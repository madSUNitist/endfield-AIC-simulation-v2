"""Forge of the Sky unit — advanced aerial forging.

Not yet implemented.
"""

from ..base import Base


class ForgeOfTheSky(Base):
    """Placeholder forge of the sky unit."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ForgeOfTheSky.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ForgeOfTheSky.request_upstream")

    def _accept_item(self, item) -> bool:
        raise NotImplementedError("ForgeOfTheSky._accept_item")
