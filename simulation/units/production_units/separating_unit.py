"""Separating unit — separates mixed input streams.

Not yet implemented.
"""

from ..base import Base


class SeparatingUnit(Base):
    """Placeholder separating unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("SeparatingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("SeparatingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("SeparatingUnit._accept_item")
