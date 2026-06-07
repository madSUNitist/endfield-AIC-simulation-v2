"""Pipe-bridge unit — transports fluids across gaps.

Not yet implemented.
"""

from ...base import Base


class PipeBridge(Base):
    """Placeholder pipe bridge unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PipeBridge.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PipeBridge.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PipeBridge._accept_item")
