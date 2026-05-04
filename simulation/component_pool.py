from typing import Dict, Tuple, Optional

from .base import Base
from ._types import Coordinate

"""
(0, 0)
 +-x-(+1, 0)-------> x
 |   x (+2, -1)
 |     x (+3, -2)
 |       x (+4, -3)
 |
 |
 |
 |
 v
 y
"""
class ComponentPool(object):
    components: Dict[Tuple[int, int], Base]
    def __init__(self, components: Dict[Tuple[int, int], Base]) -> None:
        self.components = components
    
    def __getitem__(self, key: Coordinate) -> Base:
        return self.components[key]

    def get(self, key: Coordinate, default: Optional[Base] = None) -> Optional[Base]:
        return self.components.get(key, default)
    
    