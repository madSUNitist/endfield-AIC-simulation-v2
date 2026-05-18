"""Unloader that accepts items and places them into an inventory."""

from ..base import Base
from ..._id_gen import IDGen
from ...items.inventory import Inventory
from ...items.item import Item


class DepotUnloader(Base):
    """A depot unloader that pushes received items into an inventory."""

    def __init__(self, comp_id: int, *, id_gen: IDGen,
                 inventory: Inventory) -> None:
        """Initialise a depot unloader.

        Args:
            comp_id: Unique numeric identifier.
            id_gen: Generator for unique item IDs.
            inventory: The target inventory to push items into.
        """
        super().__init__(comp_id)
        self._id_gen = id_gen
        self._inv = inventory

    def can_pull(self) -> bool:
        """Check whether this component can provide an item.

        Returns:
            Always False — depot unloaders never provide items.
        """
        return False

    def fulfill_requests(self) -> None:
        """Depot unloaders do not initiate pulls; they only accept items."""
        ...

    def request_upstream(self) -> None:
        """Request an item from the first upstream if it can pull."""
        if self.upstreams and self.upstreams[0].can_pull():
            self.upstreams[0].add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        """Push the item into the inventory.

        Args:
            item: The item to store.

        Returns:
            True if the item was accepted, False if the inventory is full.
        """
        return self._inv.push(item)
