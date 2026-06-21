"""Splitter unit — distributes items from one input to multiple outputs.

Holds a single-slot buffer and uses distance-prioritized round-robin:
Convergers always get highest priority group.  Foreign downstreams
(connected later by others) are served before distance groups.
Within each group, 2-3-1 RR (increment before select) is used.
"""

from ....items.item import Item
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



    def can_pull(self) -> bool:
        """Check whether the buffer holds an item.

        Returns:
            True if the buffer is occupied.
        """
        return self._buffer is not None

    def fulfill_requests(self) -> None:
        """Grant one item to a pull requester.

        Foreign downstreams (not in _owner_downstreams) are served first.
        Then owner downstreams are tried by distance-priority 2-3-1 RR.
        """
        if self._buffer is None:
            self.pull_requests.clear()
            return
        if not self.pull_requests:
            return

        owner_ids: set[int] = {id(d) for d in self._owner_downstreams}

        for i, req in enumerate(self.pull_requests):
            if id(req) not in owner_ids:
                self.pull_requests.pop(i)
                item = self._buffer
                self._buffer = None
                if not req._accept_item(item):
                    self._buffer = item
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
