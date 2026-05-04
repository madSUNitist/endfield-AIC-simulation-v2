from typing import Sequence

from .._types import Coordinate, Coverage
from .._enums import Direction
from ..component_pool import ComponentPool


class Base(object):
    in_degree:  int
    out_degree: int
    
    upstreams:   Sequence["Base"]
    downstreams: Sequence["Base"]
    
    def __init__(self, pos: Coordinate, pool: ComponentPool) -> None:
        self.in_degree  = 0
        self.out_degree = 0
        self.upstreams   = []
        self.downstreams = []
        
        x, y = pos
        for direction, (dx, dy) in (
            (Direction.LEFT, (-1, 0)), 
            (Direction.RIGHT, (1, 0)), 
            (Direction.UP, (0, -1)), 
            (Direction.DOWN, (0, 1))
        ):
            component = pool.get((x + dx, y + dy))
    
    def _request(self):
        pass