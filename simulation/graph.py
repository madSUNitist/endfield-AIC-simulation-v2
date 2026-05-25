"""Connection graph built from a Layout.

Three-pass construction:
  1. Instantiate components, build occupancy grid.
  2. Connect ports via direction matching + bilateral verification:
     for each port, locate the target cell; verify the target has a
     compatible counter-port facing back toward us.
  3. Kahn topological sort for deterministic tick order.

The two-phase tick runs phase1 (sinks→sources) then phase2 (sources→sinks).
"""

from typing import Dict, Tuple, Set, List

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
        components: Component instances in placement order.
        coord_idx: Maps grid origin to its index in ``components``.
        order: Topologically-sorted component indices.
        order_coords: Topologically-sorted component origins (parallel to ``order``).
    """

    layout: Layout
    components: List[Base]
    coord_idx: Dict[Vec, int]
    order: List[int]
    order_coords: List[Vec]

    def __init__(self, layout: Layout) -> None:
        """Build graph from a Layout.

        Pass 1 — instantiate all components and record occupied cells.
        Pass 2 — bilateral port matching: for each port, find the
          neighbouring component and verify it has a compatible counter-port.
        Pass 3 — Kahn topological sort.

        Args:
            layout: A fully validated Layout instance.
        """
        self.layout = layout

        self.components: List[Base] = []
        self.coord_idx: Dict[Vec, int] = {}
        self.idx_coord: Dict[int, Vec] = {}
        self.order: List[int] = []
        self.order_coords: List[Vec] = []

        comp_map: Dict[int, int] = {}
        cell_origin: Dict[Vec, Vec] = {}
        origin_cells: Dict[Vec, Set[Vec]] = {}

        # Pass 1
        for idx, pl in enumerate(layout.get_all_components()):
            self.idx_coord[idx] = pl.pos
            self.coord_idx[pl.pos] = idx

            comp = get_component(pl.component_type, idx, **pl.config)
            comp.component_type = pl.component_type
            self.components.append(comp)
            comp_map[comp.id] = idx

            cov, _ = get_metadata(pl.component_type, **pl.config)
            cells: Set[Vec] = set()
            for offset in cov.cells(pl.rotation):
                cell = pl.pos + offset
                cell_origin[cell] = pl.pos
                cells.add(cell)
            origin_cells[pl.pos] = cells

        # Pass 2
        edges: Set[Tuple[Vec, Vec]] = set()

        for coord, idx in self.coord_idx.items():
            comp = self.components[idx]
            comp_type, rotation = layout[coord]
            cfg = layout.get_config(coord)
            _, ports = get_metadata(comp_type, **cfg)

            for port_type, port_offset, port_dir in ports:
                world_offset = port_offset @ rotation
                world_dir = port_dir @ rotation
                port_cell = coord + world_offset
                target = port_cell.towards(world_dir)

                target_origin = cell_origin.get(target)
                if target_origin is None:
                    continue

                target_comp = self.components[self.coord_idx[target_origin]]
                target_type, target_rotation = layout[target_origin]
                if not self._has_compatible_counterpart(
                    target_origin, target_type, target_rotation,
                    coord, port_type, origin_cells, layout,
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
        for comp in self.components:
            comp.finalize()

    def tick(self) -> None:
        """Execute one simulation tick.

        Phase 1 (order = sinks → sources):
          fulfil_requests() + request_upstream() for each component.
        Phase 2 (reverse order, sources → sinks):
          default no-op; overridden for zero-tick forwarding.
        """
        for idx in self.order:
            self.components[idx].phase1()
        for idx in reversed(self.order):
            self.components[idx].phase2()

    def _build_order(self, comp_map: Dict[int, int]) -> None:
        """BFS layered Kahn topological sort from sinks backward toward sources.

        Each layer collects all nodes whose immediate downstreams have
        already been processed, producing a sink-distance metric naturally
        aligned with topo_index (0 = sink, higher = farther from sink).
        Within each layer, nodes are ordered by placement index.

        Args:
            comp_map: Maps component ID to its index in ``components``.
        """
        n = len(self.components)
        out_deg = [len(c.downstreams) for c in self.components]

        layer = sorted(i for i, d in enumerate(out_deg) if d == 0)

        while layer:
            next_layer: list[int] = []
            for idx in layer:
                self.order.append(idx)
                self.order_coords.append(self.idx_coord[idx])
                comp = self.components[idx]
                for up in comp.upstreams:
                    uc = comp_map.get(up.id)
                    if uc is None:
                        continue
                    if out_deg[uc] > 0:
                        out_deg[uc] -= 1
                        if out_deg[uc] == 0:
                            next_layer.append(uc)
            layer = sorted(next_layer)

        # Cycle fallback: any remaining unvisited nodes
        remaining = sorted(i for i, d in enumerate(out_deg) if d > 0)
        if remaining:
            self.order.extend(remaining)
            for idx in remaining:
                self.order_coords.append(self.idx_coord[idx])

        layers: dict[int, int] = {}
        for idx in self.order:
            comp = self.components[idx]
            if not comp.downstreams:
                layers[idx] = 0
            else:
                dc_ids: list[int] = []
                for d in comp.downstreams:
                    did = comp_map.get(d.id)
                    if did is not None and did in layers:
                        dc_ids.append(did)
                layers[idx] = 0 if not dc_ids else 1 + max(layers[c] for c in dc_ids)

        for idx, l in layers.items():
            self.components[idx].topo_index = l

    @staticmethod
    def _has_compatible_counterpart(
        target_origin: Vec,
        target_type: ComponentType,
        target_rotation: Rotation,
        our_origin: Vec,
        our_port_type: LinkType,
        origin_cells: Dict[Vec, Set[Vec]],
        layout: Layout,
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
            layout: The Layout instance (used to look up per-component config).

        Returns:
            True if the target has a counter-port facing back toward us.
        """
        needed = LinkType.INPUT if our_port_type is LinkType.OUTPUT else LinkType.OUTPUT
        cfg = layout.get_config(target_origin)
        _, ports = get_metadata(target_type, **cfg)
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
