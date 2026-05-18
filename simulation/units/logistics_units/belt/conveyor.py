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
        """Initialise a conveyor belt.

        Args:
            comp_id: Unique numeric identifier.
            length: Number of slots. Defaults to 4.
            **kwargs: Additional arguments (ignored by the constructor).
        """
        super().__init__(comp_id)
        self._slots: List[Optional[Item]] = [None] * length
        self._count = 0
        self._accept_pos: int = length - 1

    @property
    def _length(self) -> int:
        """Return the number of slots."""
        return len(self._slots)

    def add_link(self, component: Base, link_type: LinkType) -> None:
        """Register a link.  Conveyors accept at most one downstream.

        Args:
            component: The component to link.
            link_type: Whether the link is INPUT, OUTPUT, or NONE.
        """
        if link_type is LinkType.OUTPUT:
            assert len(self.downstreams) == 0
        super().add_link(component, link_type)

    def can_pull(self) -> bool:
        """Check whether the tail slot holds an item.

        Returns:
            True if the tail (index 0) is occupied.
        """
        return self._slots[0] is not None

    def fulfill_requests(self) -> None:
        """Pop the tail item and hand it to the first pull requester.

        If the downstream rejects the item the slot is restored.
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

    def self_update(self) -> None:
        """Advance each item one slot toward the tail (index 0).

        Scans from index 1 upward so every item moves at most one
        slot per tick.  Resets ``_accept_pos`` to the head.
        """
        for i in range(1, self._length):
            if self._slots[i - 1] is None and self._slots[i] is not None:
                self._slots[i - 1] = self._slots[i]
                self._slots[i] = None
        self._accept_pos = self._length - 1

    def request_upstream(self) -> None:
        """Request from upstream if the head slot is empty."""
        if self._slots[self._length - 1] is None and self.upstreams:
            if self.upstreams[0].can_pull():
                self.upstreams[0].add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        """Accept an item into the conveyor head.

        Uses ``_accept_pos`` to support multiple calls per tick by
        writing to progressively earlier slots.  Falls back to a
        linear scan if ``_accept_pos`` is stale.

        Args:
            item: The item to insert.

        Returns:
            True if the item was accepted, False if the belt is full.
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
        """Return a copy of the slot array for rendering.

        Returns:
            List of length *length* where index 0 is the tail.
        """
        return list(self._slots)
