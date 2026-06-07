"""Conduit-outlet unit — fluid output to depot.

Not yet implemented.
"""

from ..base import Base


class ConduitOutlet(Base):
    """Placeholder conduit outlet unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ConduitOutlet.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ConduitOutlet.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ConduitOutlet._accept_item")
