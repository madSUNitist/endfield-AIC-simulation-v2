"""Conduit-inlet unit — fluid input from depot.

Not yet implemented.
"""

from ..base import Base


class ConduitInlet(Base):
    """Placeholder conduit inlet unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ConduitInlet.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ConduitInlet.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ConduitInlet._accept_item")
