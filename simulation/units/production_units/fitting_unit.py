"""Fitting unit — assembles components together.

Not yet implemented.
"""

from ..base import Base


class FittingUnit(Base):
    """Placeholder fitting unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("FittingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("FittingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("FittingUnit._accept_item")
