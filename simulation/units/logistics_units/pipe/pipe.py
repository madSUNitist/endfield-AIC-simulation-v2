"""Pipe unit — transports fluids along a path.

Not yet implemented.
"""

from ...base import Base


class Pipe(Base):
    """Placeholder pipe unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("Pipe.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("Pipe.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("Pipe._accept_item")
