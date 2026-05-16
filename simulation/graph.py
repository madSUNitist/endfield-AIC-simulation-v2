from typing import Dict, Tuple, Set, List

from .units.base import Base
from .utils import Vec
from .layout import Layout
from .mappings import get_metadata, get_components
from ._enums import LinkType


class Graph(object):
    components: Dict[Vec, Base]
    order: List[Vec]

    def __init__(self, layout: Layout) -> None:
        self.layout = layout

        # Pass 1: instantiate components, build cell -> origin reverse lookup
        self.components = {}
        self.order = []
        comp_map: Dict[int, Vec] = {}
        cell_to_origin: Dict[Vec, Vec] = {}

        for idx, (coord, (comp_type, rotation)) in enumerate(layout.get_all_components()):
            comp = get_components(comp_type, idx)
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

        # Pass 3: build topological order from terminal nodes backward
        self._build_order(comp_map)

    def _build_order(self, comp_map: Dict[int, Vec]) -> None:
        terminals = [coord for coord, comp in self.components.items()
                     if comp.out_degree == 0]

        visiting: Set[Vec] = set()
        visited: Set[Vec] = set()

        def dfs(coord: Vec) -> None:
            if coord in visited:
                return
            if coord in visiting:
                return  # cycle cut

            visiting.add(coord)
            comp = self.components[coord]

            for up in comp.upstreams:
                up_coord = comp_map.get(up.id)
                if up_coord is not None:
                    dfs(up_coord)

            visiting.remove(coord)
            visited.add(coord)
            self.order.append(coord)

        for t in terminals:
            if t not in visited:
                dfs(t)

        # sweep remaining nodes not reachable from any terminal (isolated cycles)
        for coord in self.components:
            if coord not in visited:
                dfs(coord)
    