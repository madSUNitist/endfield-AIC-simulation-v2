from typing import Dict, Tuple


class ComponentPool(object):
    components: Dict[Tuple[int, int], Component]
    def __init__(self, components: Dict[Tuple[int, int], Component]) -> None:
        self.components = components
    
    