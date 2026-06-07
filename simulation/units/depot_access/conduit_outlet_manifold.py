"""Conduit-outlet-manifold unit — multi-destination fluid output to depot.

Not yet implemented.
"""

from ..base import Base


class ConduitOutletManifold(Base):
    """Placeholder conduit outlet manifold unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ConduitOutletManifold.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ConduitOutletManifold.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ConduitOutletManifold._accept_item")
