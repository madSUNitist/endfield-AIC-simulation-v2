"""Item type definition for simulation items.

An Item is a unique instance of a particular item type, identified by a
numeric ID and a hashable type tag.
"""

from typing import Hashable

class Item(object):
    """A unique item instance with a type and identifier."""

    def __init__(self, item_id: int, item_type: Hashable):
        """Args:
            item_id: Unique numeric identifier for this item.
            item_type: Hashable tag representing the item category.
        """
        self.id = item_id
        self.type = item_type
    
    def __hash__(self) -> int:
        return (self.id, self.type).__hash__()