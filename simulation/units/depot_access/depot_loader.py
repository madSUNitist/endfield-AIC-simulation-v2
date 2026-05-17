"""Loader that pulls items of a specific type from an inventory and pushes
them downstream on request.
"""

from typing import Optional

from ..base import Base
from ..._id_gen import IDGen
from ...items.inventory import Inventory
from ...items.item import Item


class DepotLoader(Base):
    """A depot loader that extracts items of a fixed type from an inventory."""

    def __init__(self, comp_id: int, *, id_gen: IDGen,
                 inventory: Inventory, item_type: object) -> None:
        """Args:
            comp_id: Unique numeric identifier for this component.
            id_gen: Generator for unique item IDs.
            inventory: The source inventory to pull items from.
            item_type: The item type this loader handles.
        """
        super().__init__(comp_id)
        self._id_gen = id_gen
        self._inv = inventory
        self.item_type = item_type

    def can_pull(self) -> bool:
        """True when the source inventory has items of the configured type."""
        return self._inv.count(self.item_type) > 0

    def fulfill_requests(self) -> None:
        """Pop one item from the inventory and hand it to the next requester."""
        if not self.pull_requests:
            return
        item = self._inv.pop(self.item_type)
        if item is None:
            return
        requester = self.pull_requests.pop(0)
        if not requester._accept_item(item):
            self._inv.push(item)

    def request_upstream(self) -> None:
        """This loader is a source; no upstream requests."""
        ...

    def _accept_item(self, item: object) -> bool:
        """Depot loaders never accept incoming items."""
        return False
