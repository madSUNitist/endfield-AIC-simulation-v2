"""Splitter unit — distributes items from one input to multiple outputs.

Holds a single-slot buffer and uses round-robin across downstreams
to serve pull requests.
"""

from ....items.item import Item
from ...base import Base


class Splitter(Base):
    """1-to-N item distribution with single-slot buffer and RR downstream."""

    def __init__(self, comp_id: int) -> None:
        super().__init__(comp_id)
        self._buffer: Item | None = None
        self._rr_idx: int = 0

    def can_pull(self) -> bool:
        return self._buffer is not None

    def fulfill_requests(self) -> None:
        if self._buffer is None:
            self.pull_requests.clear()
            return
        if not self.pull_requests:
            return
        n = len(self.downstreams)
        for _ in range(n):
            target = self.downstreams[self._rr_idx]
            self._rr_idx = (self._rr_idx + 1) % n
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
        if self._buffer is not None or not self.upstreams:
            return
        if self.upstreams[0].can_pull():
            self.upstreams[0].add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        if self._buffer is not None:
            return False
        self._buffer = item
        return True
