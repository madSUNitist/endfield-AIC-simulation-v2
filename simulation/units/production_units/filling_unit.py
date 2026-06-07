"""Filling unit — fills containers with materials.

Not yet implemented.
"""

from ..base import Base


class FillingUnit(Base):
    """Placeholder filling unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("FillingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("FillingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("FillingUnit._accept_item")
