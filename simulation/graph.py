"""Connection graph built from a Layout.

Three-pass construction:
  1. Instantiate components, build occupancy grid.
  2. Connect ports via direction matching + bilateral verification:
     for each port, locate the target cell; verify the target has a
     compatible counter-port facing back toward us.
  3. Kahn topological sort for deterministic tick order.

The two-phase tick runs phase1 (sinks→sources) then phase2 (sources→sinks).
"""

from typing import Dict, Tuple, Set, List, Optional
import heapq

from .units.base import Base
from .utils import Vec
from .layout import Layout
from .mappings import get_metadata, get_components
from ._enums import ComponentType, LinkType, Rotation


def _has_compatible_counterpart(
    target_comp: Base,
    target_origin: Vec,
    target_type: ComponentType,
    target_rotation: Rotation,
    our_origin: Vec,
    our_port_type: LinkType,
    origin_cells: Dict[Vec, Set[Vec]],
    cfgs: Dict[Vec, dict],
) -> bool:
    """Verify that the target component has a port of the opposite type
    facing back toward our occupied cells.

    This prevents one-way connections (e.g. unloader → unloader)
    that would never transfer items.
    """
    needed = LinkType.INPUT if our_port_type is LinkType.OUTPUT else LinkType.OUTPUT
    _, ports = get_metadata(target_type, **cfgs.get(target_origin, {}))
    our_set = origin_cells.get(our_origin)
    if our_set is None:
        return False
    for tp_type, tp_offset, tp_dir in ports:
        if tp_type is not needed:
            continue
        world_offset = tp_offset @ target_rotation
        world_dir = tp_dir @ target_rotation
        tp_target = (target_origin + world_offset).towards(world_dir)
        if tp_target in our_set:
            return True
    return False


class Graph(object):
    """Directed graph of connected simulation components.

    Provides deterministic tick execution via Kahn topological order
    and a two-phase (reverse/forward) tick loop.

    Attributes:
        components: Map from grid origin to component instance.
        order: Topologically-sorted coordinate list (sources first).
    """

    components: Dict[Vec, Base]
    order: List[Vec]

    def __init__(self, layout: Layout,
                 comp_configs: Optional[Dict[Vec, dict]] = None) -> None:
        """Build graph from a Layout.

        Pass 1 — instantiate all components and record occupied cells.
        Pass 2 — bilateral port matching: for each port, find the
          neighbouring component and verify it has a compatible counter-port.
        Pass 3 — Kahn topological sort.
        """
        self.layout = layout
        self._comp_configs = comp_configs or {}

        self.components = {}
        self.order = []
        comp_map: Dict[int, Vec] = {}
        cell_to_origin: Dict[Vec, Vec] = {}
        origin_cells: Dict[Vec, Set[Vec]] = {}
        cfgs = self._comp_configs

        # Pass 1
        for idx, (coord, (comp_type, rotation)) in enumerate(layout.get_all_components()):
            cfg = cfgs.get(coord, {})
            comp = get_components(comp_type, idx, **cfg)
            comp.component_type = comp_type
            self.components[coord] = comp
            comp_map[comp.id] = coord

            cov, _ = get_metadata(comp_type, **cfg)
            cells: Set[Vec] = set()
            for offset in cov.cells(rotation):
                cell = coord + offset
                cell_to_origin[cell] = coord
                cells.add(cell)
            origin_cells[coord] = cells

        # Pass 2
        edges: Set[Tuple[Vec, Vec]] = set()

        for coord, comp in self.components.items():
            comp_type, rotation = layout[coord]
            cfg = cfgs.get(coord, {})
            _, ports = get_metadata(comp_type, **cfg)

            for port_type, port_offset, port_dir in ports:
                world_offset = port_offset @ rotation
                world_dir = port_dir @ rotation
                port_cell = coord + world_offset
                target = port_cell.towards(world_dir)

                target_origin = cell_to_origin.get(target)
                if target_origin is None:
                    continue

                target_comp = self.components[target_origin]
                target_type, target_rotation = layout[target_origin]
                if not _has_compatible_counterpart(
                    target_comp, target_origin, target_type, target_rotation,
                    coord, port_type, origin_cells, cfgs,
                ):
                    continue

                if port_type is LinkType.OUTPUT:
                    edge = (coord, target_origin)
                    if edge not in edges:
                        comp.add_link(target_comp, LinkType.OUTPUT)
                        target_comp.add_link(comp, LinkType.INPUT)
                        edges.add(edge)
                else:
                    edge = (target_origin, coord)
                    if edge not in edges:
                        comp.add_link(target_comp, LinkType.INPUT)
                        target_comp.add_link(comp, LinkType.OUTPUT)
                        edges.add(edge)

        # Pass 3
        self._build_order(comp_map)

    def tick(self) -> None:
        """Execute one simulation tick.

        Phase 1 (reverse order, sinks → sources):
          fulfil_requests() + request_upstream() for each component.
        Phase 2 (forward order, sources → sinks):
          default no-op; overridden for zero-tick forwarding.
        """
        for coord in reversed(self.order):
            self.components[coord].phase1()
        for coord in self.order:
            self.components[coord].phase2()

    def _build_order(self, comp_map: Dict[int, Vec]) -> None:
        """Kahn topological sort with tie-breaking by (x, y) coordinate.

        Falls back to picking the minimum remaining coordinate when
        the dependency graph has cycles.
        """
        in_deg: Dict[Vec, int] = {}
        for coord, comp in self.components.items():
            in_deg[coord] = len(comp.upstreams)

        heap: List[Tuple[int, int, Vec]] = []
        for coord, d in in_deg.items():
            if d == 0:
                heap.append((coord.x, coord.y, coord))
        heapq.heapify(heap)

        while heap:
            _, _, coord = heapq.heappop(heap)
            self.order.append(coord)

            for down in self.components[coord].downstreams:
                dc = comp_map.get(down.id)
                if dc is None:
                    continue
                if in_deg[dc] > 0:
                    in_deg[dc] -= 1
                    if in_deg[dc] == 0:
                        heapq.heappush(heap, (dc.x, dc.y, dc))

            if not heap:
                remaining = [c for c, d in in_deg.items() if d > 0]
                if remaining:
                    pick = min(remaining, key=lambda c: (c.x, c.y))
                    in_deg[pick] = 0
                    heapq.heappush(heap, (pick.x, pick.y, pick))
