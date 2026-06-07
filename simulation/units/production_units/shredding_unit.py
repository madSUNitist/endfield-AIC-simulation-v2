"""Shredding unit — shreds items into base materials.

Not yet implemented.
"""

from ..base import Base


class ShreddingUnit(Base):
    """Placeholder shredding unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ShreddingUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ShreddingUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ShreddingUnit._accept_item")
