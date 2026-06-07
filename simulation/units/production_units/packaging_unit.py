"""Packaging unit — packages products for storage or export.

Not yet implemented.
"""

from ..base import Base


class PackagingUnit(Base):
    """Placeholder packaging unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PackagingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PackagingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PackagingUnit._accept_item")
