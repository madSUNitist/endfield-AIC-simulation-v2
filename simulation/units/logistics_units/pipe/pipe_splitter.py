"""Pipe-splitter unit — distributes fluid from one input to multiple outputs.

Not yet implemented.
"""

from ...base import Base


class PipeSplitter(Base):
    """Placeholder pipe splitter unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PipeSplitter.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PipeSplitter.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PipeSplitter._accept_item")
