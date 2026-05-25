"""Inventory of fixed-size slots, each holding an ItemStack.

Items are pushed into the first compatible or empty slot, and popped
from the first slot matching an optional type filter.
"""

from typing import List, Optional

from .._id_gen import IDGen
from .item import Item
from .itemstack import ItemStack


class Inventory(object):
    """A fixed-size inventory of item stacks."""

    def __init__(self, slots: int, id_gen: IDGen,
                 defaults: Optional[dict] = None) -> None:
        """Initialise an inventory with a fixed number of slots.

        Args:
            slots: Number of stack slots in the inventory.
            id_gen: Generator for unique item IDs.
            defaults: Optional dict mapping item types to initial counts,
                      used to pre-fill slots.
        """
        self._slots: List[Optional[ItemStack]] = [None] * slots
        self._id_gen = id_gen
        if defaults:
            for i, (t, n) in enumerate(defaults.items()):
                if i >= slots:
                    break
                self._slots[i] = ItemStack(t, id_gen, capacity=max(n, 1), count=n)

    def push(self, item: Item) -> bool:
        """Insert an item into the first compatible or empty slot.

        Args:
            item: The item to push.

        Returns:
            True if the item was accepted, False if all slots are full or
            incompatible.
        """
        for i, slot in enumerate(self._slots):
            if slot is None:
                new_stack = ItemStack(item.type, self._id_gen)
                new_stack.push(item)
                self._slots[i] = new_stack
                return True
            if slot.type == item.type and slot.push(item):
                return True
        return False

    def pop(self, item_type: object = None) -> Optional[Item]:
        """Remove and return an item from the first matching slot.

        Args:
            item_type: Optional type filter. If None, any item type matches.

        Returns:
            An Item if one was found, or None if no matching items exist.
        """
        for i, slot in enumerate(self._slots):
            if slot is not None and (item_type is None or slot.type == item_type):
                item = slot.pop()
                if item is not None:
                    if slot._count == 0:
                        self._slots[i] = None
                    return item
        return None

    def count(self, item_type: object = None) -> int:
        """Return the total item count for the given type (or all types).

        Args:
            item_type: Optional type filter. If None, counts all items.

        Returns:
            Total number of items across all matching slots.
        """
        total = 0
        for slot in self._slots:
            if slot is not None and (item_type is None or slot.type == item_type):
                total += slot._count
        return total

    def is_full(self) -> bool:
        """Check whether every slot is occupied and at its capacity.

        Returns:
            True if every slot has an ItemStack whose count has reached
            its capacity.
        """
        return all(
            slot is not None and slot._count >= slot.capacity
            for slot in self._slots
        )

    def snapshot(self) -> list[dict[str, str | int] | None]:
        """Return all slot contents in order, preserving slot positions.

        Each non-empty slot is ``{"type": <str>, "count": <int>}``;
        empty slots are ``None``.
        """
        result: list[dict[str, str | int] | None] = []
        for slot in self._slots:
            if slot is None:
                result.append(None)
            else:
                result.append({"type": str(slot.type), "count": slot._count})
        return result

    def __len__(self) -> int:
        """Return the total number of slots (occupied or empty)."""
        return len(self._slots)
