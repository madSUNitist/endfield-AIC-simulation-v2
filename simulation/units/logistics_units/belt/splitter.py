"""Splitter unit — distributes items from one input to multiple outputs.

Holds a single-slot buffer and uses distance-prioritized round-robin:
Convergers get highest priority (shared first group); remaining
downstreams are grouped by topo_index (distance to sink).
Within each group, 2-3-1 RR (increment before select) is used.
"""

from collections import defaultdict

from ....items.item import Item
from ...._enums import ComponentType
from ...base import Base


class Splitter(Base):
    """1-to-N item distribution with single-slot buffer and distance-priority RR."""

    def __init__(self, comp_id: int) -> None:
        """Initialise a splitter with an empty buffer.

        Args:
            comp_id: Unique numeric identifier.
        """
        super().__init__(comp_id)
        self._buffer: Item | None = None

    def _build_distance_groups(self) -> None:
        """Override: Convergers get the first (highest) priority group.
        Remaining downstreams are grouped by topo_index (distance to sink),
        same as the base implementation.
        """
        convergers = [d for d in self._original_downstreams
                      if getattr(d, 'component_type', None) is ComponentType.LOGISTICS_BELT_CONVERGER]
        normal = [d for d in self._original_downstreams if d not in convergers]

        buckets: dict[int, list[Base]] = defaultdict(list)
        for d in normal:
            buckets[d.topo_index].append(d)

        groups: list[list[Base]] = []
        if convergers:
            groups.append(convergers)
        groups.extend(buckets[k] for k in sorted(buckets))

        self._distance_groups = groups
        self._distance_rr = [0] * len(self._distance_groups)

    def can_pull(self) -> bool:
        """Check whether the buffer holds an item.

        Returns:
            True if the buffer is occupied.
        """
        return self._buffer is not None

    def fulfill_requests(self) -> None:
        """Grant one item to a pull requester via distance-priority 2-3-1 RR.

        Groups downstreams by topo_index (distance to sink).  Only the
        nearest group is tried; if all its members reject, the next
        group is attempted.  Within each group, 2-3-1 RR is used.
        """
        if self._buffer is None:
            self.pull_requests.clear()
            return
        if not self.pull_requests:
            return

        for gidx, group in enumerate(self._distance_groups):
            n = len(group)
            if n == 0:
                continue
            for _ in range(n):
                self._distance_rr[gidx] = (self._distance_rr[gidx] + 1) % n
                target = group[self._distance_rr[gidx]]
                for i, req in enumerate(self.pull_requests):
                    if req is target:
                        self.pull_requests.pop(i)
                        item = self._buffer
                        self._buffer = None
                        if not target._accept_item(item):
                            self._buffer = item
                        return
        self.pull_requests.clear()

    def request_upstream(self) -> None:
        """Request an item from the first upstream if buffer is empty."""
        if self._buffer is not None or not self.upstreams:
            return
        if self.upstreams[0].can_pull():
            self.upstreams[0].add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        """Accept an item into the single-slot buffer.

        Args:
            item: The item to accept.

        Returns:
            True if the buffer was empty and the item was stored.
        """
        if self._buffer is not None:
            return False
        self._buffer = item
        return True
