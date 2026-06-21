"""Converger unit — merges items from multiple inputs to one output.

Holds a single-slot buffer.  Prefers dedicated upstreams (out_degree==1)
over shared upstreams (out_degree>1).  Among same-priority upstreams,
picks the first in connection order (upstreams list) that has items.
"""

from ....items.item import Item
from ...base import Base


class Converger(Base):
    """N-to-1 item merge component with single-slot buffer."""

    def __init__(self, comp_id: int) -> None:
        """Initialise a converger with an empty buffer.

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
        """Hand the buffered item to the first pull requester."""
        if self._buffer is None or not self.pull_requests:
            return
        requester = self.pull_requests.pop(0)
        item = self._buffer
        self._buffer = None
        if not requester._accept_item(item):
            self._buffer = item

    def request_upstream(self) -> None:
        """Request from upstreams.

        When a shared upstream (out_degree>1) is available: broadcast
        to all, letting insert-order priority determine delivery.
        When all upstreams are dedicated: single-request to first
        available in connection order.
        """
        if self._buffer is not None:
            return

        for up in self.upstreams:
            up.pull_requests = [r for r in up.pull_requests if r is not self]

        has_shared = any(up.out_degree > 1 and up.can_pull() for up in self.upstreams)

        if has_shared:
            for up in self.upstreams:
                if up.can_pull():
                    up.add_pull(self)
        else:
            for up in self.upstreams:
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
