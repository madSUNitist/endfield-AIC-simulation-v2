"""Protocol Stash — configurable item buffer with 3 × 3 coverage.

Holds a single-slot pass-through buffer backed by an independent
Inventory (6 slots × 50 capacity).  Items are first placed in the
buffer; if downstream demand exists they are forwarded immediately,
otherwise they are stored in the inventory.

**Zero-tick passthrough:**  When an item arrives via `_accept_item`
and a downstream is ready, it is forwarded in the same tick without
intermediate buffering.
"""

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
        super().__init__(comp_id)
        self._buffer: Optional[Item] = None
        self._inv = inventory
        self._rr_idx: int = 0

    def can_pull(self) -> bool:
        return self._buffer is not None or self._inv.count() > 0

    def fulfill_requests(self) -> None:
        """Grant one item to the first pull requester.

        Prefers the single-slot buffer; falls back to inventory.
        Uses round-robin across multiple downstreams.
        """
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
        n = len(self.downstreams)
        for _ in range(n):
            target = self.downstreams[self._rr_idx]
            self._rr_idx = (self._rr_idx + 1) % n
            if target in self.pull_requests:
                if target._accept_item(item):
                    self.pull_requests.clear()
                    return
                break
        # Downstream rejected → put back
        if self._buffer is None:
            self._buffer = item
        else:
            self._inv.push(item)

    def request_upstream(self) -> None:
        """Pull from upstreams if buffer space is available."""
        if self._buffer is not None and self._inv.is_full():
            return
        for up in self.upstreams:
            if up.can_pull():
                up.add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        """Zero-tick passthrough: try downstream first, then buffer,
        then inventory.
        """
        for down in self.downstreams:
            if down._accept_item(item):
                return True
        if self._buffer is None:
            self._buffer = item
            return True
        if not self._inv.is_full():
            self._inv.push(item)
            return True
        return False