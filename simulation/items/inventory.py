from typing import List, Optional

from .._id_gen import IDGen
from .item import Item
from .itemstack import ItemStack


class Inventory(object):
    def __init__(self, slots: int, id_gen: IDGen,
                 defaults: Optional[dict] = None) -> None:
        self._slots: List[Optional[ItemStack]] = [None] * slots
        self._id_gen = id_gen
        if defaults:
            for i, (t, n) in enumerate(defaults.items()):
                if i >= slots:
                    break
                self._slots[i] = ItemStack(t, id_gen, capacity=max(n, 1), count=n)

    def push(self, item: Item) -> bool:
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
        for i, slot in enumerate(self._slots):
            if slot is not None and (item_type is None or slot.type == item_type):
                item = slot.pop()
                if item is not None:
                    if slot._count == 0:
                        self._slots[i] = None
                    return item
        return None

    def __len__(self) -> int:
        return len(self._slots)
