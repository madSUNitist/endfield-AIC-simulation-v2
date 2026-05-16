from typing import Dict, Tuple, Set, List, Optional
import heapq

from .units.base import Base
from .utils import Vec
from .layout import Layout
from .mappings import get_metadata, get_components
from ._enums import LinkType


class Graph(object):
    components: Dict[Vec, Base]
    order: List[Vec]

    def __init__(self, layout: Layout,
                 comp_configs: Optional[Dict[Vec, dict]] = None) -> None:
        self.layout = layout

        # Pass 1: instantiate components, build cell -> origin reverse lookup
        self.components = {}
        self.order = []
        comp_map: Dict[int, Vec] = {}
        cell_to_origin: Dict[Vec, Vec] = {}
        cfgs = comp_configs or {}

        for idx, (coord, (comp_type, rotation)) in enumerate(layout.get_all_components()):
            comp = get_components(comp_type, idx, **cfgs.get(coord, {}))
            comp.component_type = comp_type
            self.components[coord] = comp
            comp_map[comp.id] = coord

            cov, _ = get_metadata(comp_type)
            for offset in cov.coverage:
                cell_to_origin[coord + (offset @ rotation)] = coord

        # Pass 2: scan ports and build directed edges
        edges: Set[Tuple[Vec, Vec]] = set()

        for coord, comp in self.components.items():
            comp_type, rotation = layout[coord]
            _, ports = get_metadata(comp_type)

            for port_type, port_offset, port_dir in ports:
                world_offset = port_offset @ rotation
                world_dir = port_dir @ rotation
                target = (coord + world_offset).towards(world_dir)

                target_origin = cell_to_origin.get(target)
                if target_origin is None:
                    continue

                target_comp = self.components[target_origin]
                if port_type is LinkType.OUTPUT:
                    edge = (coord, target_origin)
                    if edge not in edges:
                        comp.add_link(target_comp, LinkType.OUTPUT)
                        target_comp.add_link(comp, LinkType.INPUT)
                        edges.add(edge)
                else:  # LinkType.INPUT
                    edge = (target_origin, coord)
                    if edge not in edges:
                        comp.add_link(target_comp, LinkType.INPUT)
                        target_comp.add_link(comp, LinkType.OUTPUT)
                        edges.add(edge)

        # Pass 3: forward topological sort (Kahn) with stable ordering
        self._build_order(comp_map)

    def tick(self) -> None:
        for coord in reversed(self.order):
            comp = self.components[coord]
            comp.fulfill_requests()
            comp.request_upstream()

    def _build_order(self, comp_map: Dict[int, Vec]) -> None:
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
    