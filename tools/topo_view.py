"""Visualize topological order for a blueprint."""

import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from simulation.factory import Factory
from simulation.utils import Vec


def _abbr(c):
    n = c.__class__.__name__
    return n.replace("ProtocolStash", "Stash").replace("DepotLoader", "Load") \
            .replace("Converger", "Cvrg").replace("Splitter", "Splt") \
            .replace("Conveyor", "Conv")


if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <blueprint.json>")
    sys.exit(1)

blob = json.loads(Path(sys.argv[1]).read_text())
cfg = {"name": "debug", "ticks": 1, "inventory": {"ore": 9999}, "components": blob}
fac = Factory(cfg)

g = fac.graph
n = len(g.order)

id_to_coord: dict[int, Vec] = {}
labels: dict[Vec, str] = {}

for coord, idx in g.coord_idx.items():
    comp = g.components[idx]
    id_to_coord[comp.id] = coord
    labels[coord] = f"{_abbr(comp)}#{comp.id}({coord.x},{coord.y})"

print(f"Topological order ({n} components, sinks → sources):\n")

for i, idx in enumerate(g.order):
    comp = g.components[idx]
    coord = g.idx_coord[idx]
    us = [id_to_coord.get(u.id) for u in comp.upstreams]
    ds = [id_to_coord.get(d.id) for d in comp.downstreams]
    ustr = ", ".join(labels.get(u, "?") for u in us if u) or "—"
    dstr = ", ".join(labels.get(d, "?") for d in ds if d) or "—"
    topo = comp.topo_index
    print(f"  [{i:2d}]  {labels[coord]:30s}  topo={topo}  ← {ustr:35s}  → {dstr}")

# Check Stash#1's downstream topo_index values
stash_coords: list[Vec] = []
for coord, idx in g.coord_idx.items():
    if g.components[idx].__class__.__name__ == 'ProtocolStash':
        stash_coords.append(coord)

if stash_coords:
    print(f"\n--- ProtocolStash downstream topo_index ---")
    for sc in stash_coords:
        sc_comp = g.components[g.coord_idx[sc]]
        print(f"  Stash{sc_comp.id}({sc.x},{sc.y}):")
        for d in sc_comp.downstreams:
            dc = id_to_coord.get(d.id)
            if dc:
                print(f"    topo={g.components[g.coord_idx[dc]].topo_index}  {labels[dc]}")
            else:
                print(f"    topo=?  ?")

# Graphviz
try:
    from graphviz import Digraph
    dot = Digraph("topo", format="png")
    dot.attr(rankdir="LR", splines="ortho", fontsize="10")
    for i, idx in enumerate(g.order):
        comp = g.components[idx]
        coord = g.idx_coord[idx]
        dot.node(f"C{comp.id}", f"{comp.__class__.__name__}\\n({coord.x},{coord.y})\ntopo={comp.topo_index}",
                 shape="box", style="filled", fillcolor="#e0f0ff")
    for coord, idx in g.coord_idx.items():
        comp = g.components[idx]
        for down in comp.downstreams:
            dot.edge(f"C{comp.id}", f"C{down.id}")
    out_path = Path(__file__).parent / "topo_graph"
    dot.render(out_path, format="png", cleanup=True)
    print(f"\nGraphviz saved: {out_path}.png")
except ImportError:
    print("\n(Install graphviz for visual output)")
