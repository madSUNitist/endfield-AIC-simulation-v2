from typing import Hashable

class Item(object):
    def __init__(self, item_id: int, item_type: Hashable):
        self.id = item_id
        self.type = item_type
    
    def __hash__(self) -> int:
        return (self.id, self.type).__hash__()