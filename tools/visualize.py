"""Visualize component graphs built from test layouts.

Usage: uv run python tools/visualize.py
       uv run python tools/visualize.py --no-graphviz
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.utils import Vec
from simulation._enums import ComponentType as CT, Rotation as R
from simulation.layout import Layout
from simulation.graph import Graph


TEST_CASES: list[tuple[str, dict[Vec, tuple[CT, R]]]] = []


def _add(name: str, layout: dict[Vec, tuple[CT, R]]) -> None:
    TEST_CASES.append((name, layout))


_add("Simple Belt Line", {
    Vec(0, 0): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(0, 1): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
})

_add("Splitter", {
    Vec(0, 0):   (CT.LOGISTICS_BELT_SPLITTER, R.ROT_0),
    Vec(0, -1):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(-1, 0):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(0, 1):   (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(1, 0):   (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
})

_add("Converger", {
    Vec(0, 0):   (CT.LOGISTICS_BELT_CONVERGER, R.ROT_0),
    Vec(-1, 0):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(0, -1):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(1, 0):   (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(0, 1):   (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
})

_add("Depot Line", {
    Vec(0, 0): (CT.DEPOT_ACCESS_DEPOT_LOADER, R.ROT_0),
    Vec(0, 1): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(0, 2): (CT.DEPOT_ACCESS_DEPOT_UNLOADER, R.ROT_0),
})

_add("Protocol Stash", {
    Vec(0, 0):  (CT.DEPOT_ACCESS_PROTOCOL_STASH, R.ROT_0),
    Vec(0, -1): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(1, -1): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(2, -1): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(0, 3):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(1, 3):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
    Vec(2, 3):  (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_0),
})

_add("Rotated Belt Line", {
    Vec(0, 0): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_1),
    Vec(1, 0): (CT.LOGISTICS_BELT_CONVEYOR, R.ROT_1),
})


def _fmt(v: Vec) -> str:
    return f"({v.x},{v.y})"


def show_text(name: str, layout_dict: dict[Vec, tuple[CT, R]]) -> None:
    layout = Layout(layout_dict)
    graph = Graph(layout)

    rev: dict = {comp: coord for coord, comp in graph.components.items()}

    print(f"\n=== {name} ===")
    for coord, comp in graph.components.items():
        ctype, rot = layout[coord]
        up = ", ".join(f"[{u.id}]{_fmt(rev[u])}" for u in comp.upstreams)
        down = ", ".join(f"[{d.id}]{_fmt(rev[d])}" for d in comp.downstreams)
        print(f"  [{comp.id}] {type(comp).__name__} @{_fmt(coord)} {rot.name}  "
              f"upstreams=[{up}]  downstreams=[{down}]")
    order_str = ", ".join(f"[{graph.components[c].id}]{_fmt(c)}" for c in graph.order)
    print(f"  order=[{order_str}]")


def show_graphviz(name: str, layout_dict: dict[Vec, tuple[CT, R]],
                  output_dir: Path) -> None:
    from graphviz import Digraph  # type: ignore[import-untyped]

    layout = Layout(layout_dict)
    graph = Graph(layout)

    dot = Digraph(name=name, format="png")
    dot.attr(rankdir="BT")

    for coord, comp in graph.components.items():
        label = f"{type(comp).__name__}#{comp.id}\\n{_fmt(coord)}"
        dot.node(str(comp.id), label)

    for coord, comp in graph.components.items():
        for down in comp.downstreams:
            dot.edge(str(comp.id), str(down.id))

    stem = output_dir / f"out_{name.lower().replace(' ', '_')}"
    try:
        dot.render(str(stem), cleanup=True)
        print(f"  -> saved {stem}.png")
    except Exception as e:
        print(f"  -> graphviz render skipped: {e}")


def main() -> None:
    use_graphviz = "--no-graphviz" not in sys.argv
    output_dir = Path(__file__).parent

    for name, layout_dict in TEST_CASES:
        show_text(name, layout_dict)
        if use_graphviz:
            show_graphviz(name, layout_dict, output_dir)


if __name__ == "__main__":
    main()
