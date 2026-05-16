from ..base import Base
from ..._id_gen import IDGen
from ...items.inventory import Inventory
from ...items.item import Item


class DepotUnloader(Base):
    def __init__(self, comp_id: int, *, id_gen: IDGen,
                 inventory: Inventory) -> None:
        super().__init__(comp_id)
        self._id_gen = id_gen
        self._inv = inventory

    def fulfill_requests(self) -> None:
        ...

    def request_upstream(self) -> None:
        if self.upstreams:
            self.upstreams[0].add_pull(self)

    def _accept_item(self, item: Item) -> bool:
        return self._inv.push(item)
