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

from .units.base import Base
from .utils import Vec
from .layout import Layout
from .mappings import get_metadata, get_component
from ._enums import ComponentType, LinkType, Rotation


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

        Args:
            layout: A fully validated Layout instance.
            comp_configs: Optional per-origin config dicts forwarded to
                ``get_component`` and ``get_metadata``.
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
            comp = get_component(comp_type, idx, **cfg)
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
                if not self._has_compatible_counterpart(
                    target_origin, target_type, target_rotation,
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

        # Finalize: sort downstreams and build group tables
        for comp in self.components.values():
            comp.finalize()

    def tick(self) -> None:
        """Execute one simulation tick.

        Phase 1 (order = sinks → sources):
          fulfil_requests() + request_upstream() for each component.
        Phase 2 (reverse order, sources → sinks):
          default no-op; overridden for zero-tick forwarding.
        """
        for coord in self.order:
            self.components[coord].phase1()
        for coord in reversed(self.order):
            self.components[coord].phase2()

    def _build_order(self, comp_map: Dict[int, Vec]) -> None:
        """BFS layered topological sort from sinks backward toward sources.

        Each layer collects all nodes whose immediate downstreams have
        already been processed, producing a sink-distance metric naturally
        aligned with topo_index (0 = sink, higher = farther from sink).
        Within each layer, nodes are ordered by (x, y) for determinism.

        Args:
            comp_map: Maps component ID to its grid origin coordinate.
        """
        out_deg: Dict[Vec, int] = {}
        for coord, comp in self.components.items():
            out_deg[coord] = len(comp.downstreams)

        layer = sorted(
            (coord for coord, d in out_deg.items() if d == 0),
            key=lambda c: (c.x, c.y),
        )

        while layer:
            next_layer: list[Vec] = []
            for coord in layer:
                self.order.append(coord)
                for up in self.components[coord].upstreams:
                    uc = comp_map.get(up.id)
                    if uc is None:
                        continue
                    if out_deg[uc] > 0:
                        out_deg[uc] -= 1
                        if out_deg[uc] == 0:
                            next_layer.append(uc)
            layer = sorted(next_layer, key=lambda c: (c.x, c.y))

        # Cycle fallback: any remaining unvisited nodes
        remaining = sorted(
            (c for c, d in out_deg.items() if d > 0),
            key=lambda c: (c.x, c.y),
        )
        if remaining:
            self.order.extend(remaining)

        layers: dict[Vec, int] = {}
        for coord in self.order:
            comp = self.components[coord]
            if not comp.downstreams:
                layers[coord] = 0
            else:
                dc = [comp_map.get(d.id) for d in comp.downstreams]
                dc = [c for c in dc if c is not None and c in layers]
                # Empty dc means this is a terminal or a cycle-cut node → topo=0
                layers[coord] = 0 if not dc else 1 + max(layers[c] for c in dc)

        for coord, l in layers.items():
            self.components[coord].topo_index = l

    @staticmethod
    def _has_compatible_counterpart(
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

        Args:
            target_origin: Grid origin of the candidate neighbour.
            target_type: ComponentType of the neighbour.
            target_rotation: Rotation of the neighbour.
            our_origin: Grid origin of *this* component.
            our_port_type: The port type we are matching against.
            origin_cells: Maps each origin to its set of occupied cells.
            cfgs: Per-origin config dicts.

        Returns:
            True if the target has a counter-port facing back toward us.
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