"""Planting unit — plants seeds or saplings.

Not yet implemented.
"""

from ..base import Base


class PlantingUnit(Base):
    """Placeholder planting unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PlantingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PlantingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PlantingUnit._accept_item")
