"""FastAPI backend: loads simulation, exposes REST API."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.factory import Factory
from simulation.placement import Placement
from simulation.utils import Vec
from simulation._enums import ComponentType, Rotation
from simulation.mappings import get_metadata, get_type, get_type_name, TYPE_NAMES

logger = logging.getLogger("server")
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI()


@app.middleware("http")
async def _global_exception_handler(request: Request, call_next):
    """Catch unhandled exceptions and return a generic error response."""
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled exception in %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Internal server error"},
        )


# ── Pydantic models ────────────────────────────────────────────────

class CompPlacement(BaseModel):
    """A single component to place in a custom layout."""
    pos: Optional[list[int]] = Field(None, description="Grid origin [x, y] (not used by conveyors)")
    type: str = Field(..., description="Component type name, e.g. 'conveyor'")
    rot: str = Field("ROT_0", description="Rotation ROT_0…ROT_3")
    item: Optional[str] = Field(None, description="Item type (depot_loader only)")
    path: Optional[list[list[int]]] = Field(None, description="Polyline waypoints (conveyor only)")
    direction_in: Optional[str] = Field(None, description="Input port direction (conveyor only)")
    direction_out: Optional[str] = Field(None, description="Output port direction (conveyor only)")
    inventory: Optional[dict[str, int]] = Field(None, description="Initial inventory (protocol_stash only)")

class LayoutRequest(BaseModel):
    """Request body for /api/layout — defines a full custom simulation."""
    components: list[CompPlacement] = Field(..., description="List of components to place")
    inventory: dict[str, int] = Field(default_factory=dict, description="Initial item counts for depot loaders")

class TickRequest(BaseModel):
    """Request body for /api/tick."""
    n: int = Field(1, description="Number of ticks to advance")

class ValidatePathRequest(BaseModel):
    """Request body for /api/validate-path — check a single conveyor against existing layout."""
    path: list[list[int]] = Field(..., description="Polyline waypoints of the proposed conveyor")
    direction_in: str = Field(..., description="Input port direction")
    direction_out: str = Field(..., description="Output port direction")

# ── Global simulation state ─────────────────────────────────────────

_factory: Optional[Factory] = None
_current_tick: int = 0
_config: Optional[dict] = None

# ── Mappings ────────────────────────────────────────────────────────

_EXCLUDE_TYPES = {"belt_bridge", "item_control_port"}

_CATEGORIES: dict[str, str] = {
    "depot_loader":   "depot_access",
    "depot_unloader": "depot_access",
    "protocol_stash": "depot_access",
    "conveyor":       "logistics_units",
    "splitter":       "logistics_units",
    "converger":      "logistics_units",
    "belt_bridge":    "logistics_units",
    "item_control_port": "logistics_units",
}

_CATEGORY_LABELS: dict[str, str] = {
    "depot_access":   "Depot Access",
    "logistics_units": "Logistics Units",
}

_COLORS: dict[str, str] = {
    "depot_loader":   "#4CAF50",
    "depot_unloader": "#f44336",
    "protocol_stash": "#2196F3",
    "conveyor":       "#9E9E9E",
    "splitter":       "#FF9800",
    "converger":      "#9C27B0",
    "belt_bridge":    "#607D8B",
    "item_control_port": "#00BCD4",
}

_LABELS: dict[str, str] = {
    "depot_loader":   "Loader",
    "depot_unloader": "Unloader",
    "protocol_stash": "Stash",
    "conveyor":       "Conveyor",
    "splitter":       "Splitter",
    "converger":      "Converger",
    "belt_bridge":    "Bridge",
    "item_control_port": "CtrlPort",
}

# ── Build response data ─────────────────────────────────────────────

def _find_entry(coord: Vec) -> dict:
    """Look up the original config entry for a component by its origin.

    Args:
        coord: Grid origin of the component.

    Returns:
        The matching config dict entry, or an empty dict if not found.
    """
    if _config is None:
        return {}
    for entry in _config.get("components", []):
        if "path" in entry:
            if Vec(*entry["path"][0]) == coord:
                return entry
        elif "pos" in entry:
            if Vec(*entry["pos"]) == coord:
                return entry
    return {}


def _entry_kwargs(entry: dict) -> dict:
    """Extract conveyor-specific kwargs from a config entry.

    Args:
        entry: A component config dict.

    Returns:
        Dict with keys ``path``, ``direction_in``, ``direction_out``
        if present in the entry.
    """
    return {k: entry[k] for k in ("path", "direction_in", "direction_out") if k in entry}


def _build_components() -> tuple[list[dict], dict[int, list[int]]]:
    """Walk the component graph and build layout descriptors.

    Returns:
        Tuple of ``(comps, comp_map)`` where ``comps`` is a list of
        component descriptor dicts and ``comp_map`` maps component id
        to grid origin ``[x, y]``.
    """
    global _factory
    assert _factory is not None

    comp_map: dict[int, list[int]] = {}
    comps: list[dict] = []

    for coord, idx in _factory.graph.coord_idx.items():
        comp = _factory.graph.components[idx]
        ct = getattr(comp, "component_type", None)
        if ct is None:
            continue
        rot = _factory.layout[coord][1]

        type_name = get_type_name(ct)
        if type_name in _EXCLUDE_TYPES:
            continue

        entry = _find_entry(coord)
        kwargs = _entry_kwargs(entry)
        cov, ports = get_metadata(ct, **kwargs)
        cells = []
        for offset in cov.cells(rot):
            wc = coord + offset
            cells.append([wc.x, wc.y])

        port_list = []
        for port_type, port_offset, port_dir in ports:
            wo = port_offset @ rot
            wd = port_dir @ rot
            port_list.append({
                "type": port_type.name.lower(),
                "cell": [coord.x + wo.x, coord.y + wo.y],
                "dir": list(wd.value),
            })

        label = _LABELS.get(type_name, type_name)
        extra: dict[str, object] = {}
        if entry:
            if "item" in entry:
                label += f"({entry['item']})"
                extra["item"] = entry["item"]
            if "inventory" in entry:
                extra["inventory"] = entry["inventory"]
            if "stash_slots" in entry:
                extra["stash_slots"] = entry["stash_slots"]
            if "direction_in" in entry:
                extra["direction_in"] = entry["direction_in"]
                extra["direction_out"] = entry["direction_out"]

        comps.append({
            "id": comp.id,
            "type": type_name,
            "label": label,
            "pos": [coord.x, coord.y],
            "rot": rot.name,
            "cells": cells,
            "ports": port_list,
            "color": _COLORS.get(type_name, "#888"),
            **extra,
        })
        comp_map[comp.id] = [coord.x, coord.y]

    return comps, comp_map


def _build_edges(comps: list[dict], comp_map: dict[int, list[int]]) -> list[dict]:
    """Build the edge list from downstreams in the component graph.

    Args:
        comps: Component descriptor list (from ``_build_components``).
        comp_map: Component id → grid origin ``[x, y]``.

    Returns:
        List of ``{from, to}`` edge dicts connecting closest cell pairs.
    """
    global _factory
    assert _factory is not None

    edges = []
    for comp in _factory.graph.components:
        for down in comp.downstreams:
            to_pos = comp_map.get(down.id)
            if not to_pos:
                continue

            from_cells = _find_cells_by_id(comps, comp.id)
            to_cells = _find_cells_by_id(comps, down.id)

            best = None
            best_dist = 1e9
            for fc in from_cells:
                for tc in to_cells:
                    d = (fc[0] - tc[0]) ** 2 + (fc[1] - tc[1]) ** 2
                    if d < best_dist:
                        best_dist = d
                        best = (fc, tc)
            if best:
                edges.append({"from": best[0], "to": best[1]})

    return edges


def _find_cells_by_id(comps: list[dict], comp_id: int) -> list[list[int]]:
    """Find the cell list for a component by its id.

    Args:
        comps: Component descriptor list.
        comp_id: The component id to look up.

    Returns:
        List of ``[x, y]`` cells, or empty list if not found.
    """
    for c in comps:
        if c["id"] == comp_id:
            return c["cells"]
    return []


def _compute_viewport(comps: list[dict]) -> dict:
    """Compute a bounding viewport from all component cells.

    Args:
        comps: Component descriptor list.

    Returns:
        Viewport dict with keys ``x0, y0, w, h``.
    """
    all_cells: list[list[int]] = []
    for c in comps:
        all_cells.extend(c["cells"])
    if not all_cells:
        return {"x0": -3, "y0": -3, "w": 6, "h": 6}

    xs = [c[0] for c in all_cells]
    ys = [c[1] for c in all_cells]
    x0 = min(xs) - 2
    y0 = min(ys) - 2
    x1 = max(xs) + 2
    y1 = max(ys) + 2
    return {"x0": x0, "y0": y0, "w": x1 - x0 + 1, "h": y1 - y0 + 1}


def build_layout() -> dict:
    """Build the layout response dict for the frontend.

    Iterates all components in the graph and produces the
    ``components``, ``edges``, and ``viewport`` payload.

    Returns:
        A dict with keys ``components`` (list of component descriptors),
        ``edges`` (list of ``{from, to}``), and ``viewport``.
    """
    comps, comp_map = _build_components()
    edges = _build_edges(comps, comp_map)
    viewport = _compute_viewport(comps)
    return {"components": comps, "edges": edges, "viewport": viewport}


# ── Component state builders (per-type handlers) ──────────────────

def _build_conveyor_state(comp: Any, coord: Vec) -> dict:
    """Build state dict for a Conveyor component (slot map)."""
    global _factory
    assert _factory is not None
    ct, rot = _factory.layout[coord]
    entry = _find_entry(coord)
    kwargs = _entry_kwargs(entry)
    cov, _ = get_metadata(ct, **kwargs)
    cell_offsets = cov.cells(rot)
    slot_map = {}
    n = len(cell_offsets)
    for i, s in enumerate(comp._slots):
        if i < n:
            cell = coord + cell_offsets[n - 1 - i]
            k = f"{cell.x},{cell.y}"
            slot_map[k] = {"type": str(s.type), "id": s.id} if s is not None else None
    return {"type": "conveyor", "slot_map": slot_map}


def _build_buffer_state(comp: Any, type_name: str) -> dict:
    """Build state dict for a single-buffer component (Splitter/Converger/Stash)."""
    b = comp._buffer
    state: dict = {"type": type_name}
    state["buffer"] = {"type": str(b.type), "id": b.id} if b is not None else None
    return state


def _build_stash_inventory_state(comp: Any) -> dict:
    """Extract protocol_stash private inventory snapshot."""
    return {"inventory_slots": comp._inv.snapshot()}


def _build_loader_state(comp: Any) -> dict:
    """Build state dict for a DepotLoader."""
    return {
        "type": "depot_loader",
        "count": comp._inv.count(comp.item_type),
        "item_type": str(comp.item_type),
    }


def _build_unloader_state(comp: Any) -> dict:
    """Build state dict for a DepotUnloader."""
    return {
        "type": "depot_unloader",
        "count": comp._inv.count(),
    }


def build_component_state(comp: Any, coord: Vec) -> dict:
    """Build the per-tick state dict for a single component.

    Inspects the concrete component type and extracts relevant state
    (slot_map, buffer, inventory counts, etc.) for the frontend.

    Args:
        comp: The component instance.
        coord: Grid origin of the component.

    Returns:
        A state dict with type-specific keys (``slot_map``,
        ``buffer``, ``count``, ``inventory``, etc.).
    """
    global _factory
    assert _factory is not None
    from simulation._enums import ComponentType as CT

    state: dict = {"id": comp.id, "can_pull": comp.can_pull()}
    ct = getattr(comp, "component_type", None)
    if ct is None:
        return state

    if ct == CT.LOGISTICS_BELT_CONVEYOR:
        state.update(_build_conveyor_state(comp, coord))
    elif ct == CT.LOGISTICS_BELT_SPLITTER:
        state.update(_build_buffer_state(comp, "splitter"))
    elif ct == CT.LOGISTICS_BELT_CONVERGER:
        state.update(_build_buffer_state(comp, "converger"))
    elif ct == CT.DEPOT_ACCESS_PROTOCOL_STASH:
        state.update(_build_buffer_state(comp, "protocol_stash"))
        state.update(_build_stash_inventory_state(comp))
    elif ct == CT.DEPOT_ACCESS_DEPOT_LOADER:
        state.update(_build_loader_state(comp))
    elif ct == CT.DEPOT_ACCESS_DEPOT_UNLOADER:
        state.update(_build_unloader_state(comp))

    return state


def build_state() -> dict:
    """Build the full tick-state response (tick number + component states
    + live shared inventory snapshot).

    Returns:
        A dict with ``tick`` (int), ``components`` (list of state dicts),
        and ``inventory`` (ordered list of slot states).
    """
    global _factory, _current_tick
    assert _factory is not None
    comps = []
    for coord, idx in _factory.graph.coord_idx.items():
        comp = _factory.graph.components[idx]
        cs = build_component_state(comp, coord)
        if cs:
            comps.append(cs)
    return {
        "tick": _current_tick,
        "components": comps,
        "inventory": _factory.inv.snapshot(),
    }


def build_full_response() -> dict:
    """Build the complete response used by /api/load, /api/layout, etc.

    Combines layout data, tick state, inventory, and a top-level
    ``ok`` flag into a single response dict.

    Returns:
        A dict with ``ok``, layout keys, ``tick``, ``inventory``,
        and ``components_state``.
    """
    global _config
    layout = build_layout()
    state = build_state()
    return {
        "ok": True,
        **layout,
        "tick": state["tick"],
        "inventory": state["inventory"],
        "components_state": state["components"],
    }

# ── Routes ──────────────────────────────────────────────────────────

@app.get("/api/cases")
def list_cases():
    """List available test case names (stems of tests/test_cases/*.json)."""
    cases_dir = Path(__file__).parent.parent / "tests" / "test_cases"
    return sorted(p.stem for p in cases_dir.glob("*.json"))


@app.post("/api/blank")
def blank_map():
    """Create a blank (empty) map with default viewport."""
    global _factory, _current_tick, _config
    _config = {
        "name": "Blank Map",
        "ticks": 99999,
        "inventory": {},
        "components": [],
    }
    _factory = Factory(_config)
    _current_tick = 0
    return build_full_response()


@app.get("/api/save")
def save_blueprint():
    """Return the current layout as a blueprint dict with components
    and inventory (backward compatible: old clients receive the new
    format; new clients parse both keys)."""
    global _config
    if _config is None:
        return {"components": [], "inventory": {}}
    return {
        "components": _config.get("components", []),
        "inventory": _config.get("inventory", {}),
    }


@app.post("/api/load-blueprint")
async def load_blueprint(request: Request):
    """Accept a blueprint (bare component array or dict with
    ``components`` + ``inventory`` keys) and load it."""
    global _factory, _current_tick, _config
    data = await request.json()
    if isinstance(data, list):
        comps = data
        inventory: dict = {}
    elif isinstance(data, dict):
        comps = data.get("components", [])
        inventory = data.get("inventory", {})
    else:
        comps = []
        inventory = {}
    _config = {
        "name": "Blueprint",
        "ticks": 99999,
        "inventory": inventory,
        "components": comps,
    }
    try:
        _factory = Factory(_config)
        _current_tick = 0
        return build_full_response()
    except Exception as e:
        logger.exception("blueprint load failed")
        return {"ok": False, "error": str(e)}


@app.get("/api/component_types")
def component_types():
    """Return palette metadata (coverage, ports, colour) for every type."""
    result = []
    for type_name in TYPE_NAMES:
        if type_name in _EXCLUDE_TYPES:
            continue
        if type_name == "conveyor":
            result.append({
                "type": "conveyor",
                "label": "Conveyor",
                "color": "#9E9E9E",
                "coverage": [1, 1],
                "ports": [
                    {"type": "input", "offset": [0, 0], "direction": "up"},
                    {"type": "output", "offset": [0, 0], "direction": "down"},
                ],
                "category": _CATEGORIES.get("conveyor", ""),
            })
            continue
        cov, ports = get_metadata(get_type(type_name))
        port_list = []
        for pt, po, pd in ports:
            port_list.append({
                "type": pt.name.lower(),
                "offset": [po.x, po.y],
                "direction": pd.name.lower(),
            })
        cw = getattr(cov, 'w', 1)
        ch = getattr(cov, 'h', 1)
        result.append({
            "type": type_name,
            "label": _LABELS.get(type_name, type_name),
            "color": _COLORS.get(type_name, "#888"),
            "coverage": [cw, ch],
            "ports": port_list,
            "category": _CATEGORIES.get(type_name, ""),
        })
    return result


@app.post("/api/load")
def load_case(req: dict):
    """Load a test case by name and return full layout + initialState."""
    global _factory, _current_tick, _config
    case_name = str(req.get("case", ""))
    if ".." in case_name or "/" in case_name or "\\" in case_name:
        return {"ok": False, "error": f"Invalid case name: {case_name}"}
    cases_dir = Path(__file__).parent.parent / "tests" / "test_cases"
    path = cases_dir / f"{case_name}.json"
    if not path.exists():
        return {"ok": False, "error": f"Case '{case_name}' not found"}
    try:
        _config = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.exception("Failed to load case %s", case_name)
        return {"ok": False, "error": f"Failed to read case: {e}"}
    assert _config is not None
    _factory = Factory(_config)
    _current_tick = 0
    return build_full_response()


def _build_config_entry(c: CompPlacement) -> dict:
    """Convert a CompPlacement Pydantic model into a raw config entry dict.

    Args:
        c: The validated placement request.

    Returns:
        A config dict suitable for Factory construction.
    """
    entry: dict = {"type": c.type}

    if c.path is not None:
        entry["path"] = c.path
        entry["direction_in"] = c.direction_in
        entry["direction_out"] = c.direction_out
    else:
        entry["pos"] = c.pos
        entry["rot"] = c.rot

    if c.type == "depot_loader":
        entry["item"] = c.item or "ore"

    if not c.inventory:
        return entry

    if c.type == "protocol_stash":
        stash_slots = _build_stash_slots(c.inventory)
        entry["stash_slots"] = stash_slots
    else:
        entry["inventory"] = c.inventory

    return entry


def _build_stash_slots(inventory: dict[str, int]) -> list[dict]:
    """Convert a type→count inventory dict into per-slot entries (max 50 per slot).

    Args:
        inventory: Mapping of item type to total count.

    Returns:
        List of ``{type, count}`` slot dicts.
    """
    slots: list[dict] = []
    slot_idx = 0
    for item_type, count in inventory.items():
        remaining = count
        while remaining > 0 and slot_idx < 6:
            per_slot = min(remaining, 50)
            slots.append({"type": item_type, "count": per_slot})
            remaining -= per_slot
            slot_idx += 1
    return slots


@app.post("/api/layout")
def set_layout(req: LayoutRequest):
    """Submit a custom layout and reset the simulation to tick 0."""
    global _factory, _current_tick, _config
    comps = [_build_config_entry(c) for c in req.components]

    _config = {
        "name": "Custom Layout",
        "ticks": 99999,
        "inventory": req.inventory or {},
        "components": comps,
    }
    try:
        _factory = Factory(_config)
        _current_tick = 0
        logger.info("layout built: %d components", len(comps))
        return build_full_response()
    except Exception as e:
        logger.exception("layout rejected: %s", e)
        return {"ok": False, "error": str(e)}


@app.post("/api/validate-path")
def validate_path(req: ValidatePathRequest):
    """Check a single conveyor path against the existing layout for overlaps."""
    global _factory
    if _factory is None:
        logger.debug("validate_path: no factory loaded")
        return {"ok": False, "error": "No layout loaded"}

    placement = Placement(
        pos=Vec(*req.path[0]),
        component_type=ComponentType.LOGISTICS_BELT_CONVEYOR,
        rotation=Rotation.ROT_0,
        config={
            "path": req.path,
            "direction_in": req.direction_in,
            "direction_out": req.direction_out,
        },
    )
    ok, error = _factory.layout.can_place(placement)
    if ok:
        logger.debug("validate_path: accepted")
    else:
        logger.debug("validate_path: rejected — %s", error)
    return {"ok": ok, "error": error}


@app.post("/api/tick")
def tick(req: TickRequest):
    """Advance the simulation by N ticks.

    Returns the new tick number and component states (slot_map,
    buffer, inventory counts).
    """
    global _factory, _current_tick
    if _factory is None:
        return {"ok": False, "error": "No simulation loaded"}
    for _ in range(req.n):
        _factory.tick()
        _current_tick += 1
    return {"ok": True, **build_state()}


@app.post("/api/reset")
def reset():
    """Reset simulation to tick 0 (re-build from the last config)."""
    global _factory, _current_tick, _config
    if _config is not None:
        _factory = Factory(_config)
        _current_tick = 0
    return {"ok": True, **build_state()}


# ── Serve static files ──────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3000, log_level="info")
