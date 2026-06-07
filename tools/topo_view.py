"""Topological order visualisation for a blueprint.

Usage:
    uv run python tools/topo_view.py tests/blueprints/A.blueprint
    uv run python tools/topo_view.py tests/blueprints/A.blueprint --output out/a_topo
    uv run python tools/topo_view.py tests/blueprints/A.blueprint --no-graphviz --no-order-chain
    uv run python tools/topo_view.py tests/blueprints/A.blueprint --fmt svg
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation._enums import ComponentType as CT, Rotation
from simulation.factory import Factory
from simulation.utils import Vec

logger = logging.getLogger("topo_view")

TYPE_NAMES: dict[CT, str] = {
    CT.DEPOT_ACCESS_DEPOT_LOADER:    "Loader",
    CT.DEPOT_ACCESS_DEPOT_UNLOADER:  "Unloader",
    CT.DEPOT_ACCESS_PROTOCOL_STASH:  "Stash",
    CT.LOGISTICS_BELT_CONVEYOR:      "Conveyor",
    CT.LOGISTICS_BELT_CONVERGER:     "Converger",
    CT.LOGISTICS_BELT_SPLITTER:      "Splitter",
    CT.LOGISTICS_BELT_BELT_BRIDGE:   "Bridge",
    CT.LOGISTICS_BELT_ITEM_CONTROL_PORT: "CtrlPort",
}

TYPE_COLORS: dict[CT, str] = {
    CT.DEPOT_ACCESS_DEPOT_LOADER:    "#c8e6c9",
    CT.DEPOT_ACCESS_DEPOT_UNLOADER:  "#ffcdd2",
    CT.DEPOT_ACCESS_PROTOCOL_STASH:  "#a5d6a7",
    CT.LOGISTICS_BELT_CONVEYOR:      "#bbdefb",
    CT.LOGISTICS_BELT_CONVERGER:     "#ffcc80",
    CT.LOGISTICS_BELT_SPLITTER:      "#ffe082",
    CT.LOGISTICS_BELT_BELT_BRIDGE:   "#e0e0e0",
    CT.LOGISTICS_BELT_ITEM_CONTROL_PORT: "#e0e0e0",
}

TYPE_BORDER: dict[CT, str] = {
    CT.DEPOT_ACCESS_DEPOT_LOADER:    "#388e3c",
    CT.DEPOT_ACCESS_DEPOT_UNLOADER:  "#d32f2f",
    CT.DEPOT_ACCESS_PROTOCOL_STASH:  "#2e7d32",
    CT.LOGISTICS_BELT_CONVEYOR:      "#1565c0",
    CT.LOGISTICS_BELT_CONVERGER:     "#e65100",
    CT.LOGISTICS_BELT_SPLITTER:      "#f9a825",
    CT.LOGISTICS_BELT_BELT_BRIDGE:   "#9e9e9e",
    CT.LOGISTICS_BELT_ITEM_CONTROL_PORT: "#9e9e9e",
}

ROT_NAMES: dict[int, str] = {0: "R0", 1: "R1", 2: "R2", 3: "R3"}

GROUP_COLORS = ["#d32f2f", "#1565c0", "#2e7d32", "#e65100", "#6a1b9a"]


def _format_coord(v: Vec) -> str:
    """Format a Vec as ``(x,y)``."""
    return f"({v.x},{v.y})"


def _format_rotation_label(rot: Rotation) -> str:
    """Format a Rotation enum to a short label like ``R0``."""
    return ROT_NAMES.get(rot.value - 1, "??")


def build_topo_data(fac: Factory) -> dict[int, dict]:
    """Extract topological data from a built Factory.

    Args:
        fac: A fully constructed Factory instance.

    Returns:
        Dict mapping component id → metadata dict with keys including
        ``id``, ``idx``, ``topo``, ``coord``, ``ctype``, ``rot``,
        ``up_ids``, ``down_ids``, ``groups``, and ``detail``.
    """
    g = fac.graph
    id_to_coord: dict[int, Vec] = {}
    data: dict[int, dict] = {}

    for coord, idx in g.coord_idx.items():
        comp = g.components[idx]
        id_to_coord[comp.id] = coord

    for i, idx in enumerate(g.order):
        comp = g.components[idx]
        coord = g.idx_coord[idx]
        ctype, rot = g.layout[coord]
        config = g.layout.get_config(coord)

        up_coords = [id_to_coord.get(u.id) for u in comp.upstreams]
        down_coords = [id_to_coord.get(d.id) for d in comp.downstreams]
        up_ids = [u.id for u in comp.upstreams]
        down_ids = [d.id for d in comp.downstreams]

        detail: dict = {}
        try:
            if ctype == CT.LOGISTICS_BELT_CONVEYOR:
                detail["len"] = config.get("length", "?")
                detail["in"] = config.get("direction_in", "?")
                detail["out"] = config.get("direction_out", "?")
            elif ctype == CT.DEPOT_ACCESS_DEPOT_LOADER:
                detail["item"] = getattr(comp, "item_type", "?")
            elif ctype == CT.DEPOT_ACCESS_PROTOCOL_STASH:
                inv = getattr(comp, "_inv", None)
                if inv is not None:
                    detail["slots"] = len(getattr(inv, "_slots", []))
        except Exception:
            logger.error("Failed to extract detail for component #%d", comp.id, exc_info=True)

        downstream_groups: list[dict] = []
        for gi, (start, end) in enumerate(comp._downstream_groups):
            member_ids = [d.id for d in comp.downstreams[start:end]]
            member_topo = comp.downstreams[start].topo_index if member_ids else -1
            downstream_groups.append({"idx": gi, "topo": member_topo, "ids": member_ids})

        data[comp.id] = {
            "id": comp.id,
            "idx": i,
            "topo": comp.topo_index,
            "coord": coord,
            "ctype": ctype,
            "rot": rot,
            "in_deg": comp.in_degree,
            "out_deg": comp.out_degree,
            "up_ids": up_ids,
            "down_ids": down_ids,
            "up_coords": up_coords,
            "down_coords": down_coords,
            "detail": detail,
            "groups": downstream_groups,
        }

    return data


# ── Text output helpers ────────────────────────────────────────────

def _render_text_table(data: dict[int, dict], order: list[int],
                       components: list) -> None:
    """Print the main topological-order table.

    Args:
        data: Topo data dict keyed by component id.
        order: Topologically-sorted component indices.
        components: Component instance list (from ``graph.components``).
    """
    print(f"  {'idx':<4s} {'id':<4s} {'topo':<5s} {'type':<10s} "
          f"{'coord':<10s} {'rot':<5s} {'in/out':<8s} {'details'}")
    print(f"  {'---':<4s} {'---':<4s} {'----':<5s} {'----':<10s} "
          f"{'-----':<10s} {'---':<5s} {'------':<8s} {'-------'}")

    for i, idx in enumerate(order):
        comp = components[idx]
        d = data[comp.id]
        ctype_name = TYPE_NAMES.get(d["ctype"], "?")
        detail_str = (
            ", ".join(f"{k}={v}" for k, v in d["detail"].items())
            if d["detail"] else "—"
        )
        io = f"{d['in_deg']}\u2192{d['out_deg']}"
        print(f"  [{i:2d}] #{d['id']:<2d} t={d['topo']:<2d}  "
              f"{ctype_name:<10s} {_format_coord(d['coord']):<10s} "
              f"{_format_rotation_label(d['rot']):<5s} "
              f"{io:<8s} {detail_str}")


def _render_text_upstreams_downstreams(data: dict[int, dict],
                                        order: list[int],
                                        components: list) -> None:
    """Print upstream/downstream relationships for each component.

    Args:
        data: Topo data dict keyed by component id.
        order: Topologically-sorted component indices.
        components: Component instance list.
    """
    print(f"\n  Upstreams / Downstreams:\n")
    for i, idx in enumerate(order):
        comp = components[idx]
        d = data[comp.id]
        ctype_name = TYPE_NAMES.get(d["ctype"], "?")
        u_str = (
            ", ".join(f"#{uid} {_format_coord(c)}"
                      for uid, c in zip(d["up_ids"], d["up_coords"]))
            if d["up_ids"] else "—"
        )
        down_parts: list[str] = []
        for did, dc in zip(d["down_ids"], d["down_coords"]):
            gi = None
            for grp in d.get("groups", []):
                if did in grp["ids"]:
                    gi = grp["idx"]
                    break
            tag = f"[g{gi}] " if gi is not None else ""
            down_parts.append(f"{tag}#{did} {_format_coord(dc)}")
        d_str = ", ".join(down_parts) if down_parts else "—"
        print(f"  [{i:2d}] #{comp.id:<2d} {ctype_name:<10s}  \u2190 {u_str}")
        print(f"         {'':12s}  \u2192 {d_str}")


def _render_text_layers(data: dict[int, dict], max_topo: int) -> None:
    """Print components grouped by ``topo_index`` layer.

    Args:
        data: Topo data dict keyed by component id.
        max_topo: Maximum topo_index value.
    """
    if max_topo < 0:
        return
    topo_buckets: dict[int, list[int]] = {t: [] for t in range(max_topo + 1)}
    for comp_id, d in data.items():
        topo_buckets[d["topo"]].append(comp_id)

    print(f"\n  Layers (by topo_index):")
    for t in range(max_topo + 1):
        ids = topo_buckets.get(t, [])
        parts = []
        for cid in ids:
            d = data[cid]
            parts.append(f"#{cid} {_format_coord(d['coord'])}")
        print(f"    topo={t}: {', '.join(parts)}")


def show_text(fac: Factory) -> None:
    """Print a full text-mode topological-order visualisation.

    Args:
        fac: A fully constructed Factory instance.
    """
    g = fac.graph
    data = build_topo_data(fac)

    n = len(g.order)
    max_topo = max(d["topo"] for d in data.values()) if data else 0

    print(f"Topological order ({n} components, sinks \u2192 sources):\n")
    _render_text_table(data, g.order, g.components)
    _render_text_upstreams_downstreams(data, g.order, g.components)
    _render_text_layers(data, max_topo)


# ── Graphviz output helpers ────────────────────────────────────────

def _build_graphviz_nodes(dot, data: dict[int, dict]) -> None:
    """Add nodes to a graphviz Digraph.

    Args:
        dot: The graphviz ``Digraph`` instance.
        data: Topo data dict keyed by component id.
    """
    for comp_id, d in data.items():
        ctype_name = TYPE_NAMES.get(d["ctype"], "?")
        detail_parts = [f"{k}={v}" for k, v in d["detail"].items()]
        detail_str = "\\n".join(detail_parts) if detail_parts else ""
        node_label = (
            f"#{d['id']} {ctype_name}\\n"
            f"{_format_coord(d['coord'])} {_format_rotation_label(d['rot'])}\\n"
            f"idx={d['idx']}  topo={d['topo']}"
        )
        if detail_str:
            node_label += f"\\n{detail_str}"
        dot.node(
            f"C{d['id']}",
            node_label,
            shape="box",
            style="filled",
            fillcolor=TYPE_COLORS.get(d["ctype"], "#f0f0f0"),
            color=TYPE_BORDER.get(d["ctype"], "#999999"),
            fontsize="9",
        )


def _build_graphviz_edges(dot, data: dict[int, dict]) -> None:
    """Add edges to a graphviz Digraph.

    Args:
        dot: The graphviz ``Digraph`` instance.
        data: Topo data dict keyed by component id.
    """
    edge_group: dict[tuple[int, int], int] = {}
    for d in data.values():
        for grp in d.get("groups", []):
            for did in grp["ids"]:
                edge_group[(d["id"], did)] = grp["idx"]

    for d in data.values():
        for down_id in d["down_ids"]:
            gi = edge_group.get((d["id"], down_id))
            attrs: dict[str, str] = {"fontsize": "7"}
            if gi is not None:
                attrs["color"] = GROUP_COLORS[gi % len(GROUP_COLORS)]
                attrs["fontcolor"] = GROUP_COLORS[gi % len(GROUP_COLORS)]
                attrs["xlabel"] = f"g{gi}"
            dot.edge(f"C{d['id']}", f"C{down_id}", **attrs)


def _add_order_chain_overlay(dot, fac: Factory) -> None:
    """Add dashed order-chain overlay arrows to the graph.

    Args:
        dot: The graphviz ``Digraph`` instance.
        fac: A fully constructed Factory instance.
    """
    g = fac.graph
    n = len(g.order)
    if n <= 1:
        return
    for i in range(n - 1):
        id_a = g.components[g.order[i]].id
        id_b = g.components[g.order[i + 1]].id
        dot.edge(
            f"C{id_a}", f"C{id_b}",
            style="dashed",
            color="#e57373",
            penwidth="0.6",
            arrowsize="0.5",
            constraint="false",
        )


def show_graphviz(fac: Factory, output: Path, fmt: str, *,
                  show_order_chain: bool = True) -> None:
    """Render a graphviz visualisation of the topological order.

    Args:
        fac: A fully constructed Factory instance.
        output: Output path (without extension).
        fmt: Output format ("png", "svg", "pdf").
        show_order_chain: Whether to include dashed order-chain arrows.
    """
    try:
        from graphviz import Digraph  # type: ignore[import-untyped]
    except ImportError:
        print("(Install graphviz for visual output)")
        return

    data = build_topo_data(fac)

    dot = Digraph("topo", format=fmt)
    dot.attr(rankdir="LR", splines="ortho", fontsize="10",
             nodesep="0.5", ranksep="1.0")

    _build_graphviz_nodes(dot, data)
    _build_graphviz_edges(dot, data)

    if show_order_chain:
        _add_order_chain_overlay(dot, fac)

    try:
        out_path = dot.render(str(output), cleanup=True)
        print(f"Graphviz saved: {out_path}")
    except Exception:
        logger.exception("Graphviz render failed for %s", output)


def main() -> None:
    """Parse command-line arguments and run topo visualisation."""
    parser = argparse.ArgumentParser(
        description="Topological order visualisation for a blueprint.")
    parser.add_argument("blueprint", type=Path, help="Blueprint JSON file")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Graphviz output path (default: tools/topo_graph)")
    parser.add_argument("--no-graphviz", action="store_true",
                        help="Skip graphviz generation")
    parser.add_argument("--fmt", type=str, default="png",
                        choices=["png", "svg", "pdf"],
                        help="Graphviz output format (default: png)")
    parser.add_argument("--no-order-chain", action="store_true",
                        help="Hide the order-chain overlay arrows")

    args = parser.parse_args()

    bp = Path(args.blueprint)
    if not bp.exists():
        print(f"Error: file not found: {bp}")
        sys.exit(1)

    try:
        raw = json.loads(bp.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.exception("Failed to parse blueprint %s", bp)
        print(f"Error: cannot read {bp}: {e}")
        sys.exit(1)

    if isinstance(raw, list):
        cfg = {"name": bp.stem, "ticks": 1, "inventory": {"ore": 9999},
               "components": raw}
    elif isinstance(raw, dict) and "components" in raw:
        cfg = raw
        cfg.setdefault("name", bp.stem)
    else:
        print(f"Error: unrecognised JSON format in {bp}")
        sys.exit(1)

    fac = Factory(cfg)

    show_text(fac)

    if not args.no_graphviz:
        out_path = args.output if args.output else Path(__file__).parent / "topo_graph"
        show_graphviz(fac, out_path, args.fmt,
                      show_order_chain=not args.no_order_chain)


if __name__ == "__main__":
    main()
