"""Water-treatment unit — treats and purifies water.

Not yet implemented.
"""

from ..base import Base


class WaterTreatmentUnit(Base):
    """Placeholder water treatment unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("WaterTreatmentUnit.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("WaterTreatmentUnit.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("WaterTreatmentUnit._accept_item")
