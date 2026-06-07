"""Moulding unit — shapes materials using moulds.

Not yet implemented.
"""

from ..base import Base


class MouldingUnit(Base):
    """Placeholder moulding unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("MouldingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("MouldingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("MouldingUnit._accept_item")
