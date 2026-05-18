"""Stack-based container for items of a single type.

An ItemStack holds a count of undifferentiated items of one type, with a
maximum capacity. Items are popped as new unique Item instances.
"""

from typing import Hashable, Optional

from .item import Item
from .._id_gen import IDGen

class ItemStack(object):
    """A stack of items of a single type with a fixed capacity."""

    def __init__(self, type: Hashable, id_gen: IDGen, capacity: int = 50, count: int = 0) -> None:
        """Initialise an item stack.

        Args:
            type: The hashable item type this stack accepts.
            id_gen: Generator for unique item IDs.
            capacity: Maximum number of items this stack can hold. Defaults to 50.
            count: Initial number of items in the stack. Defaults to 0.
        """
        self.type = type
        self.capacity = capacity
        self._count = count
        self._id_gen = id_gen
    
    def pop(self) -> Optional[Item]:
        """Remove and return one item from the stack.

        Returns:
            A new Item instance if the stack is non-empty, or None if empty.
        """
        if self._count > 0:
            self._count -= 1
            return Item(self._id_gen.next(), self.type)

        return None
    
    def push(self, item: Item) -> bool:
        """Add an item to the stack.

        Args:
            item: The item to push. Its type must match this stack's type.

        Returns:
            True if the item was accepted, False if the type mismatches or
            the stack is full.
        """
        if item.type != self.type:
            return False
        
        if self._count >= self.capacity:
            return False
    
        self._count += 1
        return True