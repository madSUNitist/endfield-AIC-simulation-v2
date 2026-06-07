"""Conduit-inlet-manifold unit — multi-source fluid input from depot.

Not yet implemented.
"""

from ..base import Base


class ConduitInletManifold(Base):
    """Placeholder conduit inlet manifold unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ConduitInletManifold.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ConduitInletManifold.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ConduitInletManifold._accept_item")
