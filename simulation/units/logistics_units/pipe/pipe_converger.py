"""Pipe-converger unit — merges fluid from multiple inputs to one output.

Not yet implemented.
"""

from ...base import Base


class PipeConverger(Base):
    """Placeholder pipe converger unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PipeConverger.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PipeConverger.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PipeConverger._accept_item")
