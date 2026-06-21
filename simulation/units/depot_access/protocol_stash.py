"""Protocol Stash — configurable item buffer with 3 × 3 coverage.

Holds a single-slot pass-through buffer backed by an independent
Inventory (6 slots × 50 capacity).  Items are first placed in the
buffer; if downstream demand exists they are forwarded immediately,
otherwise they are stored in the inventory.

**Zero-tick passthrough:**  When an item arrives via `_accept_item`
and a downstream is ready, it is forwarded in the same tick without
intermediate buffering.

**Distance-priority + connection-order RR:**  Downstreams are grouped
by topo_index (distance to sink).  Items go to the shortest-distance
group first; within each group, 1-2-3 connection-order RR is used.
Other paths stay idle until the shorter path is blocked.
"""

from typing import Optional, TYPE_CHECKING

from ..base import Base
from ..._id_gen import IDGen
from ...items.inventory import Inventory
from ...items.item import Item

if TYPE_CHECKING:
    from ...engine import Outbox


class ProtocolStash(Base):
    """Configurable storage buffer with distance-priority pass-through.

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
        self._saved_pull_requests: list[Base] = []

    def can_pull(self) -> bool:
        """Check whether the buffer or inventory has items.

        Returns:
            True if the buffer is occupied or the inventory is non-empty.
        """
        return self._buffer is not None or self._inv.count() > 0

    def fulfill_requests(self) -> None:
        """Grant items to pull requesters via distance-priority 1-2-3 RR.

        Groups downstreams by topo_index (distance to sink).  Items are
        distributed to the nearest group first; only when all members
        of that group are blocked does the stash fall back to farther
        groups.  Within each group, 1-2-3 connection-order RR is used.

        Saves the current ``pull_requests`` list for later use in
        :meth:`phase2`.
        """
        self._saved_pull_requests = list(self.pull_requests)
        if not self.pull_requests:
            return

        buf_item: Item | None = self._buffer
        self._buffer = None
        available = (1 if buf_item is not None else 0) + self._inv.count()

        if available == 0:
            return

        pr_set = set(id(r) for r in self.pull_requests)
        self.pull_requests.clear()

        for gidx, group in enumerate(self._distance_groups):
            if available == 0:
                break
            n = len(group)
            if n == 0:
                continue
            rr = self._distance_rr[gidx]
            for _ in range(n):
                if available == 0:
                    break
                target = group[rr]
                rr = (rr + 1) % n

                if id(target) not in pr_set:
                    continue

                item: Item | None
                if buf_item is not None:
                    item = buf_item
                    buf_item = None
                else:
                    item = self._inv.pop()
                assert item is not None

                if target._accept_item(item):
                    available -= 1
                    pr_set.discard(id(target))
                else:
                    if buf_item is None:
                        buf_item = item
                    else:
                        self._inv.push(item)
            self._distance_rr[gidx] = rr

        if buf_item is not None:
            if self._buffer is None:
                self._buffer = buf_item
            else:
                self._inv.push(buf_item)

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

        If pull requests exist, tries downstreams in distance-priority
        1-2-3 RR order.  Otherwise falls back to pushing to the first
        available downstream in distance-priority order.
        """
        item = self._buffer
        if item is None:
            return
        self._buffer = None

        pr_set = set(id(r) for r in self._saved_pull_requests) if self._saved_pull_requests else set()

        for gidx, group in enumerate(self._distance_groups):
            n = len(group)
            if n == 0:
                continue
            rr = self._distance_rr[gidx]
            for _ in range(n):
                target = group[rr]
                rr = (rr + 1) % n

                if self._saved_pull_requests and id(target) not in pr_set:
                    continue

                if target._accept_item(item):
                    self._distance_rr[gidx] = rr
                    return
            self._distance_rr[gidx] = rr

        if not self._inv.is_full():
            self._inv.push(item)
        else:
            self._buffer = item

    def _run_p1(self, subtick: int, outbox: "Outbox") -> None:
        self.fulfill_requests()
        self.self_update()
        if self._buffer is not None and self._inv.is_full():
            return
        for up in self.upstreams:
            if up.can_pull():
                outbox.add_pull(up)

    def _run_p2(self, subtick: int, outbox: "Outbox") -> None:
        self.phase2()
