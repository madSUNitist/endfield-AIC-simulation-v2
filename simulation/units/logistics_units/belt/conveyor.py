"""Conveyor belt unit — shift-based item transport.

Items occupy a fixed-length slot array.  At the start of each tick
an internal shift moves all items one slot toward index 0 (the exit).

Index 0 is the tail where downstream pulls are fulfilled.
Index length-1 is the head where new items from upstream are written.

`_accept_pos` enables multiple `_accept_item` calls per tick by
tracking the next available write position backward from the head.
"""

from typing import List, Optional, Sequence

from ...base import Base
from ...._enums import LinkType
from ....items.item import Item


class Conveyor(Base):
    """Fixed-length belt that shifts items one slot per tick (FIFO).

    Items enter at the head (index length-1) and exit at the tail
    (index 0).  Only one downstream is supported.
    """

    def __init__(self, comp_id: int, length: int = 4, **kwargs: object) -> None:
        super().__init__(comp_id)
        self._slots: List[Optional[Item]] = [None] * length
        self._count = 0
        self._accept_pos: int = length - 1

    @property
    def _length(self) -> int:
        return len(self._slots)

    def add_link(self, component: Base, link_type: LinkType) -> None:
        """Register a link.  Conveyors accept at most one downstream."""
        if link_type is LinkType.OUTPUT:
            assert len(self.downstreams) == 0
        super().add_link(component, link_type)

    def can_pull(self) -> bool:
        return self._slots[0] is not None

    def fulfill_requests(self) -> None:
        """Pop the tail item and hand it to the first pull requester.

        If the downstream reject the item the slot is restored.
        """
        if self._slots[0] is None or not self.pull_requests:
            return
        requester = self.pull_requests.pop(0)
        item = self._slots[0]
        self._slots[0] = None
        self._count -= 1
        if not requester._accept_item(item):
            self._slots[0] = item
            self._count += 1

    def request_upstream(self) -> None:
        """Shift all items one slot toward the tail; request from upstream.

        If the tail is occupied the shift is skipped (item exits this
        tick).
        """
        if self._slots[0] is None:
            for i in range(self._length - 1):
                self._slots[i] = self._slots[i + 1]
            self._slots[self._length - 1] = None
        self._accept_pos = self._length - 1

        if self._slots[self._length - 1] is None and self.upstreams:
            if self.upstreams[0].can_pull():
                self.upstreams[0].add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        """Accept an item into the conveyor head.

        Uses `_accept_pos` to support multiple calls per tick by
        writing to progressively earlier slots.  Falls back to a
        linear scan if `_accept_pos` is stale.
        """
        if self._count >= self._length:
            return False
        pos = self._accept_pos
        if pos < 0 or self._slots[pos] is not None:
            pos = self._length - 1
            while pos >= 0 and self._slots[pos] is not None:
                pos -= 1
            if pos < 0:
                return False
        self._slots[pos] = item
        self._count += 1
        self._accept_pos = pos - 1
        return True

    def get_snapshot(self) -> Sequence[Optional[Item]]:
        """Return the slot array (index 0 = tail) for rendering."""
        return list(self._slots)
