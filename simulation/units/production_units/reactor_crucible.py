"""Reactor crucible unit — high-temperature chemical processing.

Not yet implemented.
"""

from ..base import Base


class ReactorCrucible(Base):
    """Placeholder reactor crucible unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ReactorCrucible.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ReactorCrucible.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ReactorCrucible._accept_item")
