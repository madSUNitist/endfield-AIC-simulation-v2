"""Static visualisation of all test-case graphs.

Usage:
    uv run python tools/visualize.py
    uv run python tools/visualize.py --no-graphviz
    uv run python tools/visualize.py --output docs/
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.factory import Factory
from simulation._enums import ComponentType as CT
from simulation.utils import Vec


TEST_DIR = Path(__file__).parent.parent / "tests" / "test_cases"

_TYPE_NAMES: dict[CT, str] = {
    CT.DEPOT_ACCESS_DEPOT_LOADER:    "Loader",
    CT.DEPOT_ACCESS_DEPOT_UNLOADER:  "Unloader",
    CT.DEPOT_ACCESS_PROTOCOL_STASH:  "Stash",
    CT.LOGISTICS_BELT_CONVEYOR:      "Conveyor",
    CT.LOGISTICS_BELT_CONVERGER:     "Converger",
    CT.LOGISTICS_BELT_SPLITTER:      "Splitter",
    CT.LOGISTICS_BELT_BELT_BRIDGE:   "Bridge",
    CT.LOGISTICS_BELT_ITEM_CONTROL_PORT: "CtrlPort",
}


def _fmt(v: Vec) -> str:
    return f"({v.x},{v.y})"


def show_text(cfg: dict) -> None:
    name = cfg.get("name", "?")
    f = Factory(cfg)
    rev: dict = {}
    for coord, idx in f.graph.coord_idx.items():
        rev[f.graph.components[idx]] = coord

    print(f"\n=== {name} ===")
    for coord, idx in f.graph.coord_idx.items():
        comp = f.graph.components[idx]
        ctype, rot = f.layout[coord]
        short = _TYPE_NAMES.get(ctype, "?")
        up = ", ".join(f"[{u.id}]{_fmt(rev[u])}" for u in comp.upstreams)
        down = ", ".join(f"[{d.id}]{_fmt(rev[d])}" for d in comp.downstreams)
        print(f"  [{comp.id}] {short} @{_fmt(coord)} {rot.name}  "
              f"upstreams=[{up}]  downstreams=[{down}]")
    order_str = ", ".join(f"[{f.graph.components[f.graph.coord_idx[c]].id}]{_fmt(c)}"
                          for c in f.graph.order_coords)
    print(f"  order=[{order_str}]")


def show_graphviz(cfg: dict, output_dir: Path) -> None:
    from graphviz import Digraph  # type: ignore[import-untyped]

    name = cfg.get("name", "?")
    f = Factory(cfg)
    stem = f"out_{name.lower().replace(' ', '_')}"

    dot = Digraph(name=name, format="svg")
    dot.attr(rankdir="BT")

    for coord, idx in f.graph.coord_idx.items():
        comp = f.graph.components[idx]
        ctype, rot = f.layout[coord]
        short = _TYPE_NAMES.get(ctype, "?")
        label = f"{short}#{comp.id}\\n{_fmt(coord)}"
        dot.node(str(comp.id), label)

    for coord, idx in f.graph.coord_idx.items():
        comp = f.graph.components[idx]
        for down in comp.downstreams:
            dot.edge(str(comp.id), str(down.id))

    out = output_dir / stem
    try:
        dot.render(str(out), cleanup=True)
        print(f"  -> saved {out}.png")
    except Exception as e:
        print(f"  -> graphviz skipped: {e}")


def main() -> None:
    use_graphviz = "--no-graphviz" not in sys.argv

    try:
        i = sys.argv.index("--output")
        output_dir = Path(sys.argv[i + 1])
    except (ValueError, IndexError):
        output_dir = Path(__file__).parent

    for j in sorted(TEST_DIR.glob("*.json")):
        with j.open(encoding="utf-8") as f:
            cfg = json.load(f)
        show_text(cfg)
        if use_graphviz:
            show_graphviz(cfg, output_dir)


if __name__ == "__main__":
    main()
