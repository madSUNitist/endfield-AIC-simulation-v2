"""FastAPI backend: loads simulation, exposes REST API."""

import json
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.factory import Factory
from simulation.utils import Vec
from simulation.mappings import get_metadata, get_type, get_type_name, TYPE_NAMES

app = FastAPI()

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

class LayoutRequest(BaseModel):
    """Request body for /api/layout — defines a full custom simulation."""
    components: list[CompPlacement] = Field(..., description="List of components to place")
    inventory: dict[str, int] = Field(default_factory=dict, description="Initial item counts for depot loaders")

class TickRequest(BaseModel):
    """Request body for /api/tick."""
    n: int = Field(1, description="Number of ticks to advance")

# ── Global simulation state ─────────────────────────────────────────

_factory: Optional[Factory] = None
_current_tick: int = 0
_config: Optional[dict] = None

# ── Mappings ────────────────────────────────────────────────────────

_EXCLUDE_TYPES = {"belt_bridge", "item_control_port"}

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


def build_layout() -> dict:
    """Build the layout response dict for the frontend.

    Iterates all components in the graph and produces the
    ``components``, ``edges``, and ``viewport`` payload.

    Returns:
        A dict with keys ``components`` (list of component descriptors),
        ``edges`` (list of ``{from, to}``), and ``viewport``.
    """
    global _factory
    assert _factory is not None

    comp_map: dict[int, list[int]] = {}
    comps: list[dict] = []

    for coord, comp in _factory.graph.components.items():
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

    edges = []
    for coord, comp in _factory.graph.components.items():
        for down in comp.downstreams:
            to_pos = comp_map.get(down.id)
            if to_pos:
                from_cells = []
                for c in comps:
                    if c["id"] == comp.id:
                        from_cells = c["cells"]
                        break
                to_cells = []
                for c in comps:
                    if c["id"] == down.id:
                        to_cells = c["cells"]
                        break

                # Find closest cell pair between components
                best = None
                best_dist = 1e9
                for fc in from_cells:
                    for tc in to_cells:
                        d = (fc[0]-tc[0])**2 + (fc[1]-tc[1])**2
                        if d < best_dist:
                            best_dist = d
                            best = (fc, tc)
                if best:
                    edges.append({"from": best[0], "to": best[1]})

    # Viewport
    all_cells = []
    for c in comps:
        all_cells.extend(c["cells"])
    if not all_cells:
        viewport = {"x0": -3, "y0": -3, "w": 6, "h": 6}
    else:
        xs = [c[0] for c in all_cells]
        ys = [c[1] for c in all_cells]
        x0 = min(xs) - 2
        y0 = min(ys) - 2
        x1 = max(xs) + 2
        y1 = max(ys) + 2
        viewport = {"x0": x0, "y0": y0, "w": x1 - x0 + 1, "h": y1 - y0 + 1}

    return {"components": comps, "edges": edges, "viewport": viewport}


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
    from simulation.units.logistics_units.belt.conveyor import Conveyor
    from simulation.units.logistics_units.belt.converger import Converger
    from simulation.units.logistics_units.belt.splitter import Splitter
    from simulation.units.depot_access.protocol_stash import ProtocolStash
    from simulation.units.depot_access.depot_loader import DepotLoader
    from simulation.units.depot_access.depot_unloader import DepotUnloader

    state: dict = {"id": comp.id, "can_pull": comp.can_pull()}

    if isinstance(comp, Conveyor):
        state["type"] = "conveyor"
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
        state["slot_map"] = slot_map
    elif isinstance(comp, (Converger, Splitter)):
        state["type"] = "splitter" if isinstance(comp, Splitter) else "converger"
        b = comp._buffer
        state["buffer"] = {"type": str(b.type), "id": b.id} if b is not None else None
    elif isinstance(comp, ProtocolStash):
        state["type"] = "protocol_stash"
        b = comp._buffer
        state["buffer"] = {"type": str(b.type), "id": b.id} if b is not None else None
        state["inventory"] = comp._inv.count()
    elif isinstance(comp, DepotLoader):
        state["type"] = "depot_loader"
        state["count"] = comp._inv.count(comp.item_type)
        state["item_type"] = str(comp.item_type)
    elif isinstance(comp, DepotUnloader):
        state["type"] = "depot_unloader"
        state["count"] = comp._inv.count()

    return state


def build_state() -> dict:
    """Build the full tick-state response (tick number + component states).

    Returns:
        A dict with ``tick`` (int) and ``components`` (list of state dicts).
    """
    global _factory, _current_tick
    assert _factory is not None
    comps = []
    for coord, comp in _factory.graph.components.items():
        cs = build_component_state(comp, coord)
        if cs:
            comps.append(cs)
    return {"tick": _current_tick, "components": comps}


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
        "inventory": (_config or {}).get("inventory", {}),
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
    """Return the current layout as a bare blueprint array
    (matches the test_case component-entry format)."""
    global _config
    if _config is None:
        return []
    return _config.get("components", [])


@app.post("/api/load-blueprint")
async def load_blueprint(request: Request):
    """Accept a blueprint array (bare component entries) and load it."""
    global _factory, _current_tick, _config
    data = await request.json()
    comps = data if isinstance(data, list) else []
    _config = {
        "name": "Blueprint",
        "ticks": 99999,
        "inventory": {},
        "components": comps,
    }
    try:
        _factory = Factory(_config)
        _current_tick = 0
        return build_full_response()
    except Exception as e:
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
        })
    return result


@app.post("/api/load")
def load_case(req: dict):
    """Load a test case by name and return full layout + initialState."""
    global _factory, _current_tick, _config
    case_name = req.get("case", "")
    cases_dir = Path(__file__).parent.parent / "tests" / "test_cases"
    path = cases_dir / f"{case_name}.json"
    if not path.exists():
        return {"ok": False, "error": f"Case '{case_name}' not found"}
    _config = json.loads(path.read_text())
    _factory = Factory(_config)
    _current_tick = 0
    return build_full_response()


@app.post("/api/layout")
def set_layout(req: LayoutRequest):
    """Submit a custom layout and reset the simulation to tick 0."""
    global _factory, _current_tick, _config
    comps = []
    for c in req.components:
        entry: dict = {
            "type": c.type,
        }
        if c.path is not None:
            entry["path"] = c.path
            entry["direction_in"] = c.direction_in
            entry["direction_out"] = c.direction_out
        else:
            entry["pos"] = c.pos
            entry["rot"] = c.rot
        if c.type == "depot_loader":
            entry["item"] = c.item or "ore"
        comps.append(entry)

    _config = {
        "name": "Custom Layout",
        "ticks": 99999,
        "inventory": req.inventory or {},
        "components": comps,
    }
    try:
        _factory = Factory(_config)
        _current_tick = 0
        return build_full_response()
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
