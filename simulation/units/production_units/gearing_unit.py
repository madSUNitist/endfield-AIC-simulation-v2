"""Gearing unit — produces gear components.

Not yet implemented.
"""

from ..base import Base


class GearingUnit(Base):
    """Placeholder gearing unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("GearingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("GearingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("GearingUnit._accept_item")
