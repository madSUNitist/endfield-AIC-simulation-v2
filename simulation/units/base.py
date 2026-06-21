"""Abstract base class for all simulation components.

Each component maintains upstream/downstream links and a round-robin
pull system for item transfer.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Optional, TYPE_CHECKING

from .._enums import LinkType, ComponentType
from ..items.item import Item
from ..utils import Vec

if TYPE_CHECKING:
    from ..engine import Outbox


class Base(ABC):
    """Abstract base for a simulation unit with links and pull-request logic."""

    component_type: ComponentType

    in_degree:  int
    out_degree: int

    upstreams:   List["Base"]
    downstreams: List["Base"]

    pull_requests: List["Base"]
    pull_rr: int
    upstream_rr: int

    topo_index: int
    grid_pos: Optional[Vec]

    _downstream_groups: List[tuple[int, int]]
    _downstream_rr: List[int]
    _original_downstreams: List["Base"]
    _owner_downstreams: List["Base"]
    _distance_groups: List[List["Base"]]
    _distance_rr: List[int]
    _exec_pos: int

    _phase: int
    _active: bool

    def __init__(self, comp_id: int) -> None:
        """Initialise a component base.

        Args:
            comp_id: Unique numeric identifier for this component.
        """
        self.id = comp_id

        self.in_degree  = 0
        self.out_degree = 0
        self.upstreams   = []
        self.downstreams = []

        self.pull_requests = []
        self.pull_rr = 0
        self.upstream_rr = 0

        self.topo_index = -1
        self.grid_pos = None
        self._downstream_groups = []
        self._downstream_rr = []
        self._original_downstreams = []
        self._owner_downstreams = []
        self._distance_groups = []
        self._distance_rr = []
        self._exec_pos = -1

        self._phase = 0
        self._active = False

    def add_link(self, component: "Base", link_type: LinkType):
        """Register a link to another component.

        Updates in-degree / out-degree and appends to the corresponding
        adjacency list.

        Args:
            component: The component to link.
            link_type: Whether the link is INPUT, OUTPUT, or NONE.
        """
        match link_type:
            case LinkType.INPUT:
                self.in_degree += 1
                self.upstreams.append(component)
            case LinkType.OUTPUT:
                self.out_degree += 1
                self.downstreams.append(component)
            case LinkType.NONE:
                return

    def finalize(self) -> None:
        """Sort downstreams by topo_index and build group tables for RR.

        Called once after the topological sort is complete.
        Groups are stored as (start, end) ranges into downstreams,
        with a parallel ``_downstream_rr`` list of per-group RR indices.

        Also builds ``_distance_groups`` for priority output routing.
        """
        self._original_downstreams = list(self.downstreams)
        self.downstreams.sort(key=lambda d: d.topo_index)
        self._downstream_groups.clear()
        self._downstream_rr.clear()
        i = 0
        while i < len(self.downstreams):
            ti = self.downstreams[i].topo_index
            j = i
            while j < len(self.downstreams) and self.downstreams[j].topo_index == ti:
                j += 1
            self._downstream_groups.append((i, j))
            self._downstream_rr.append(0)
            i = j
        self._build_distance_groups()

    def _build_distance_groups(self) -> None:
        """Group original downstreams by topo_index (distance to sink), ascending.
        Within each group, connection order is preserved.

        Populates ``_distance_groups`` and ``_distance_rr``.
        """
        buckets: dict[int, list["Base"]] = defaultdict(list)
        for d in self._original_downstreams:
            buckets[d.topo_index].append(d)
        self._distance_groups = [buckets[k] for k in sorted(buckets)]
        self._distance_rr = [0] * len(self._distance_groups)

    def add_pull(self, requester: "Base") -> None:
        """Insert a downstream component at the front of the pull-request queue.

        Later requests get higher priority (inserted at front).

        Args:
            requester: The component requesting an item pull.
        """
        self.pull_requests.insert(0, requester)

    @abstractmethod
    def fulfill_requests(self) -> None:
        """Fulfill pending pull requests by transferring items downstream."""
        ...

    @abstractmethod
    def request_upstream(self) -> None:
        """Request items from upstream components."""
        ...

    def self_update(self) -> None:
        """Advance internal state (e.g. shift belt slots).

        Called after ``fulfill_requests()`` and before
        ``request_upstream()`` in Phase 1.  Default no-op.
        """
        ...

    def phase1(self) -> None:
        """Phase 1 (sinks → sources): deliver, advance, then request.

        Delegates to ``fulfill_requests()``, ``self_update()``, and
        ``request_upstream()`` in sequence.
        """
        self.fulfill_requests()
        self.self_update()
        self.request_upstream()

    def phase2(self) -> None:
        """Forward pass (sources → sinks): handle zero-tick forwarding.

        Default no-op.  Override in components that need zero-tick
        routing (e.g. :class:`ProtocolStash`).
        """

    def can_pull(self) -> bool:
        """Check whether this component currently has an item to provide.

        Returns:
            True if fulfill_requests() would be able to supply an item.
        """
        return False

    def step(self, subtick: int, outbox: "Outbox") -> None:
        """Execute the component's current phase and advance the FSM.

        Args:
            subtick: Global monotonic subtick counter.
            outbox: Write buffer for cross-component pull requests.
        """
        if self._phase == 0:
            self._run_p1(subtick, outbox)
        else:
            self._run_p2(subtick, outbox)
        self._phase = 1 - self._phase

    def _run_p1(self, subtick: int, outbox: "Outbox") -> None:
        """Phase 1: deliver, advance, request (overridden per component)."""
        raise NotImplementedError(
            f"{type(self).__name__}._run_p1"
        )

    def _run_p2(self, subtick: int, outbox: "Outbox") -> None:
        """Phase 2: zero-tick passthrough (overridden by ProtocolStash)."""
        self.phase2()

    @abstractmethod
    def _accept_item(self, item: Item) -> bool:
        """Accept an incoming item from upstream.

        Args:
            item: The item being pushed into this component.

        Returns:
            True if the item was accepted, False otherwise.
        """
        ...