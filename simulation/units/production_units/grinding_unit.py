"""Grinding unit — grinds raw materials into powder.

Not yet implemented.
"""

from ..base import Base


class GrindingUnit(Base):
    """Placeholder grinding unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("GrindingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("GrindingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("GrindingUnit._accept_item")
