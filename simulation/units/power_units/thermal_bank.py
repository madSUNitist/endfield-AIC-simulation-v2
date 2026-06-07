"""Thermal-bank unit — stores thermal energy.

Not yet implemented.
"""

from ..base import Base


class ThermalBank(Base):
    """Placeholder thermal bank unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ThermalBank.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ThermalBank.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ThermalBank._accept_item")
