"""Purification unit — purifies raw resources.

Not yet implemented.
"""

from ..base import Base


class PurificationUnit(Base):
    """Placeholder purification unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("PurificationUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("PurificationUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("PurificationUnit._accept_item")
