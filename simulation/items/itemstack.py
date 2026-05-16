from typing import Hashable, Optional

from .item import Item
from .._id_gen import IDGen

class ItemStack(object):
    def __init__(self, type: Hashable, id_gen: IDGen, capacity: int = 50, count: int = 0) -> None:
        self.type = type
        self.capacity = capacity
        self._count = count
        self._id_gen = id_gen
    
    def pop(self) -> Optional[Item]:
        if self._count > 0:
            self._count -= 1
            return Item(self._id_gen.next(), self.type)

        return None
    
    def push(self, item: Item) -> bool:
        if item.type != self.type:
            return False
        
        if self._count >= self.capacity:
            return False
    
        self._count += 1
        return True