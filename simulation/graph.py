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
        processed: Set[Vec] = set()

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

                if target_origin not in processed:
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

            comp._owner_downstreams = list(comp.downstreams)
            processed.add(coord)

        # Pass 3
        self._build_order(comp_map)

        for pos, idx in enumerate(self.order):
            self.components[idx]._exec_pos = pos

        # Finalize: sort downstreams and build group tables
        for comp in self.components:
            comp.finalize()

    def tick(self) -> None:
        """Execute one simulation tick.

        Phase 1 (order = sinks → sources):
          fulfil_requests() + self_update() + request_upstream().
        Phase 2 (reverse order, sources → sinks):
          default no-op; overridden for zero-tick forwarding.
        """
        for idx in self.order:
            self.components[idx].phase1()
        for idx in reversed(self.order):
            self.components[idx].phase2()

    def _build_order(self, comp_map: Dict[int, int]) -> None:
        """O(n²) topological sort with inline cycle breaking.

        Repeatedly picks sinks (out_deg == 0), appends them to ``order``
        sorted by placement index, and decrements upstream out-degrees.
        When no sink is available (a cycle blocks progress), a DFS along
        downstream edges discovers the cycle, cuts the edge from the
        placement-last node (sink) to the placement-first node (source),
        and continues.

        This produces a deterministic reverse-topological order (sinks
        first, sources last) even in the presence of cycles, without
        special-casing belt loops.

        Args:
            comp_map: Maps component ID to its index in ``components``.
        """
        n = len(self.components)
        out_deg = [len(c.downstreams) for c in self.components]
        cut_edges: set[tuple[int, int]] = set()  # (from_idx, to_idx)

        def _break_one_cycle() -> bool:
            """DFS from the first unvisited node with out_deg > 0.

            Cuts the edge (sink → source) where *source* is the
            placement-first node and *sink* is the placement-last node
            in the discovered cycle.  Returns True if a cycle was found
            and broken, False if no cycle remains (should not happen
            when called from the main loop).
            """
            # Pick a starting node still stuck in a cycle.
            start: int | None = None
            for i in range(n):
                if out_deg[i] > 0 and i not in visited:
                    start = i
                    break
            if start is None:
                return False

            path: list[int] = []
            path_set: set[int] = set()

            exploring: set[int] = set()  # local to this DFS pass — do NOT pollute visited

            def dfs_cycle(current: int) -> bool:
                """Walk downstreams; return True when a cycle is cut."""
                if current in path_set:
                    # Cycle detected.
                    cycle_start = path.index(current)
                    cycle = path[cycle_start:]
                    source = min(cycle)  # placement-first
                    sink = max(cycle)    # placement-last
                    cut_edges.add((sink, source))
                    out_deg[sink] -= 1
                    return True

                if current in visited or current in exploring:
                    return False

                exploring.add(current)
                path.append(current)
                path_set.add(current)

                comp = self.components[current]
                for down in comp.downstreams:
                    dc = comp_map.get(down.id)
                    if dc is None:
                        continue
                    if (current, dc) in cut_edges:
                        continue
                    if dfs_cycle(dc):
                        return True

                path.pop()
                path_set.discard(current)
                return False

            return dfs_cycle(start)

        visited: set[int] = set()

        while len(self.order) < n:
            sinks = sorted(
                i for i in range(n)
                if out_deg[i] == 0 and i not in visited
            )

            if sinks:
                for idx in sinks:
                    self.order.append(idx)
                    self.order_coords.append(self.idx_coord[idx])
                    visited.add(idx)
                    comp = self.components[idx]
                    for up in comp.upstreams:
                        uc = comp_map.get(up.id)
                        if uc is None:
                            continue
                        if (uc, idx) in cut_edges:
                            continue
                        if out_deg[uc] > 0:
                            out_deg[uc] -= 1
            else:
                if not _break_one_cycle():
                    remainder = sorted(i for i in range(n) if i not in visited)
                    for idx in remainder:
                        self.order.append(idx)
                        self.order_coords.append(self.idx_coord[idx])
                        visited.add(idx)
                    break

        layers: dict[int, int] = {}
        for idx in reversed(self.order):
            comp = self.components[idx]
            up_ids: list[int] = []
            for u in comp.upstreams:
                uid = comp_map.get(u.id)
                if uid is not None and uid in layers and (uid, idx) not in cut_edges:
                    up_ids.append(uid)
            layers[idx] = 0 if not up_ids else 1 + max(layers[c] for c in up_ids)

        for idx, l in layers.items():
            self.components[idx].topo_index = l

        self.order.sort(key=lambda idx: (-self.components[idx].topo_index, idx))
        self.order_coords = [self.idx_coord[idx] for idx in self.order]

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
