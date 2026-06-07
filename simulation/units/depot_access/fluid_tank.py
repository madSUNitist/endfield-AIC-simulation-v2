"""Fluid-tank unit — stores fluids from depot.

Not yet implemented.
"""

from ..base import Base


class FluidTank(Base):
    """Placeholder fluid tank unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("FluidTank.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("FluidTank.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("FluidTank._accept_item")
