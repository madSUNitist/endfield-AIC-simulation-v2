"""Expanded-crucible unit — high-capacity smelting.

Not yet implemented.
"""

from ..base import Base


class ExpandedCrucible(Base):
    """Placeholder expanded crucible unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ExpandedCrucible.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ExpandedCrucible.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ExpandedCrucible._accept_item")
