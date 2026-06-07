"""Refining unit — refines raw materials into purer forms.

Not yet implemented.
"""

from ..base import Base


class RefiningUnit(Base):
    """Placeholder refining unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("RefiningUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("RefiningUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("RefiningUnit._accept_item")
