"""Item-control port — interface point for inserting or extracting items.

Not yet implemented.
"""

from ...base import Base
from ....items.item import Item


class ItemControlPort(Base):
    """Placeholder item control port (manual / automation I/O)."""

    def fulfill_requests(self) -> None:
        raise NotImplementedError("ItemControlPort.fulfill_requests")

    def request_upstream(self) -> None:
        raise NotImplementedError("ItemControlPort.request_upstream")

    def _accept_item(self, item: Item) -> bool:
        raise NotImplementedError("ItemControlPort._accept_item")