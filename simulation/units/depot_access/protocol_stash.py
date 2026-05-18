"""Protocol Stash — configurable item buffer with 3 × 3 coverage.

Holds a single-slot pass-through buffer backed by an independent
Inventory (6 slots × 50 capacity).  Items are first placed in the
buffer; if downstream demand exists they are forwarded immediately,
otherwise they are stored in the inventory.

**Zero-tick passthrough:**  When an item arrives via `_accept_item`
and a downstream is ready, it is forwarded in the same tick without
intermediate buffering.
"""

from collections import defaultdict
from typing import Optional

from ..base import Base
from ..._id_gen import IDGen
from ...items.inventory import Inventory
from ...items.item import Item


class ProtocolStash(Base):
    """Configurable storage buffer with pass-through priority.

    Items flow: upstream → buffer (or immediate downstream) → inventory.
    """

    def __init__(self, comp_id: int, *,
                 id_gen: IDGen, inventory: Inventory) -> None:
        """Initialise a protocol stash.

        Args:
            comp_id: Unique numeric identifier.
            id_gen: Generator for unique item IDs.
            inventory: Backing inventory for overflow storage.
        """
        super().__init__(comp_id)
        self._buffer: Optional[Item] = None
        self._inv = inventory
        self._rr_groups: dict[int, int] = {}
        self._saved_pull_requests: list[Base] = []

    def can_pull(self) -> bool:
        """Check whether the buffer or inventory has items.

        Returns:
            True if the buffer is occupied or the inventory is non-empty.
        """
        return self._buffer is not None or self._inv.count() > 0

    def fulfill_requests(self) -> None:
        """Grant one item to pull requesters, short-path first,
        round-robin within same topo_index group.

        Saves the current ``pull_requests`` list for later use in
        :meth:`phase2`.
        """
        self._saved_pull_requests = list(self.pull_requests)
        if not self.pull_requests:
            return
        item: Item | None = None
        if self._buffer is not None:
            item = self._buffer
            self._buffer = None
        elif self._inv.count() > 0:
            item = self._inv.pop()
        else:
            return

        assert item is not None

        buckets: dict[int, list[Base]] = defaultdict(list)
        for pr in self.pull_requests:
            buckets[pr.topo_index].append(pr)

        for ti in sorted(buckets):
            group = buckets[ti]
            n = len(group)
            rr = self._rr_groups.get(ti, 0)
            for _ in range(n):
                target = group[rr % n]
                rr = (rr + 1) % n
                if target._accept_item(item):
                    self._rr_groups[ti] = rr
                    self.pull_requests.clear()
                    return
            self._rr_groups[ti] = rr

        if self._buffer is None:
            self._buffer = item
        else:
            self._inv.push(item)

    def request_upstream(self) -> None:
        """Pull from upstreams if buffer or inventory space is available."""
        if self._buffer is not None and self._inv.is_full():
            return
        for up in self.upstreams:
            if up.can_pull():
                up.add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        """Store locally — routing to downstreams happens in :meth:`phase2`.

        Args:
            item: The item to store.

        Returns:
            True if the item was accepted (buffer or inventory).
        """
        if self._buffer is None:
            self._buffer = item
            return True
        if not self._inv.is_full():
            self._inv.push(item)
            return True
        return False

    def phase2(self) -> None:
        """Route buffered item to downstreams (zero-tick passthrough).

        If pull requests exist, use short-path-first + RR routing.
        Otherwise fall back to simple push to the first available
        downstream using the group RR table.
        """
        item = self._buffer
        if item is None:
            return
        self._buffer = None

        pr = self._saved_pull_requests
        if pr:
            buckets: dict[int, list[Base]] = defaultdict(list)
            for p in pr:
                buckets[p.topo_index].append(p)
            for ti in sorted(buckets):
                group = buckets[ti]
                n = len(group)
                rr = self._rr_groups.get(ti, 0)
                for _ in range(n):
                    target = group[rr % n]
                    rr = (rr + 1) % n
                    if target._accept_item(item):
                        self._rr_groups[ti] = rr
                        return
                self._rr_groups[ti] = rr
        else:
            # No pull requests — fallback: use _downstream_groups RR
            for gidx, (start, end) in enumerate(self._downstream_groups):
                n = end - start
                if n == 0:
                    continue
                rr = self._downstream_rr[gidx]
                for _ in range(n):
                    target = self.downstreams[start + rr]
                    rr = (rr + 1) % n
                    if target._accept_item(item):
                        self._downstream_rr[gidx] = rr
                        return
                self._downstream_rr[gidx] = rr

        if not self._inv.is_full():
            self._inv.push(item)
        else:
            self._buffer = item
