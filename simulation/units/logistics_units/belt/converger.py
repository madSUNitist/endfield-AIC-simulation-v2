"""Converger unit — merges items from multiple inputs to one output.

Holds a single-slot buffer and uses round-robin selection across upstreams,
checking can_pull() before registering a pull request.
"""

from ....items.item import Item
from ...base import Base


class Converger(Base):
    """N-to-1 item merge component with a single-slot buffer and RR upstream."""

    def __init__(self, comp_id: int) -> None:
        """Initialise a converger with an empty buffer.

        Args:
            comp_id: Unique numeric identifier.
        """
        super().__init__(comp_id)
        self._buffer: Item | None = None
        self._skip_idx: int = 0

    def can_pull(self) -> bool:
        """Check whether the buffer holds an item.

        Returns:
            True if the buffer is occupied.
        """
        return self._buffer is not None

    def fulfill_requests(self) -> None:
        """Hand the buffered item to the first pull requester."""
        if self._buffer is None or not self.pull_requests:
            return
        requester = self.pull_requests.pop(0)
        item = self._buffer
        self._buffer = None
        if not requester._accept_item(item):
            self._buffer = item

    def request_upstream(self) -> None:
        """RR scan upstreams, pull from the first that can provide.

        Skips full upstreams using ``_skip_idx`` for fair round-robin.
        """
        if self._buffer is not None:
            return
        n = len(self.upstreams)
        for _ in range(n):
            up = self.upstreams[self._skip_idx]
            self._skip_idx = (self._skip_idx + 1) % n
            if up.can_pull():
                up.add_pull(self)
                return

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