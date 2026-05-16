from typing import Optional

from ..base import Base
from ..._id_gen import IDGen
from ...items.inventory import Inventory
from ...items.item import Item


class DepotLoader(Base):
    def __init__(self, comp_id: int, *, id_gen: IDGen,
                 inventory: Inventory, item_type: object) -> None:
        super().__init__(comp_id)
        self._id_gen = id_gen
        self._inv = inventory
        self.item_type = item_type

    def fulfill_requests(self) -> None:
        if not self.pull_requests:
            return
        item = self._inv.pop(self.item_type)
        if item is None:
            return
        requester = self.pull_requests.pop(0)
        if not requester._accept_item(item):
            self._inv.push(item)

    def request_upstream(self) -> None:
        ...

    def _accept_item(self, item: object) -> bool:
        return False
