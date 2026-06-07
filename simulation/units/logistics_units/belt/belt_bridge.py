"""Belt-bridge unit — transports items across gaps or between layers.

Not yet implemented.
"""

from ...base import Base
from ....items.item import Item


class BeltBridge(Base):
    """Placeholder belt bridge (elevated crossing / inter-layer belt)."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("BeltBridge.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("BeltBridge.request_upstream")

    def _accept_item(self, item: Item) -> bool:
        raise NotImplementedError("BeltBridge._accept_item")