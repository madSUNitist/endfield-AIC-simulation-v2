from typing import List, Optional, Sequence

from ...base import Base
from ...._enums import LinkType
from ....items.item import Item


class Conveyor(Base):
    def __init__(self, comp_id: int, length: int = 4, **kwargs: object) -> None:
        super().__init__(comp_id)
        self._slots: List[Optional[Item]] = [None] * length
        self._ptr = 0
        self._count = 0

    @property
    def _length(self) -> int:
        return len(self._slots)

    def add_link(self, component: Base, link_type: LinkType) -> None:
        if link_type is LinkType.INPUT:
            assert len(self.upstreams) == 0
        if link_type is LinkType.OUTPUT:
            assert len(self.downstreams) == 0
        super().add_link(component, link_type)

    def fulfill_requests(self) -> None:
        if self._count == 0 or not self.pull_requests:
            return
        tail = (self._ptr - self._count + self._length) % self._length
        if self._slots[tail] is None:
            return
        requester = self.pull_requests.pop(0)
        item = self._slots[tail]
        assert item is not None
        self._slots[tail] = None
        self._count -= 1
        if not requester._accept_item(item):
            self._slots[tail] = item
            self._count += 1

    def request_upstream(self) -> None:
        if self._count < self._length and self.upstreams:
            self.upstreams[0].add_pull(self)
        self._ptr = (self._ptr + 1) % self._length

    def _accept_item(self, item: Item) -> bool:
        if self._count >= self._length:
            return False
        slot = (self._ptr - 1 + self._length) % self._length
        self._slots[slot] = item
        self._count += 1
        return True

    def get_snapshot(self) -> Sequence[Optional[Item]]:
        cells: List[Optional[Item]] = []
        for i in range(self._length):
            idx = (self._ptr - self._count + self._length + i) % self._length
            cells.append(self._slots[idx])
        return cells
