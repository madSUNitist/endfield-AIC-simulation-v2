"""Pipe-control-port unit — interface for inserting or extracting fluid.

Not yet implemented.
"""

from ...base import Base


class PipeControlPort(Base):
    """Placeholder pipe control port unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PipeControlPort.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PipeControlPort.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PipeControlPort._accept_item")
