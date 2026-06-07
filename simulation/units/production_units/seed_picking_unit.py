"""Seed-picking unit — selects and sorts seeds.

Not yet implemented.
"""

from ..base import Base


class SeedPickingUnit(Base):
    """Placeholder seed picking unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("SeedPickingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("SeedPickingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("SeedPickingUnit._accept_item")
