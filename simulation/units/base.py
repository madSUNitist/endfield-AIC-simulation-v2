from abc import ABC, abstractmethod
from typing import List

from .._enums import LinkType, ComponentType
from ..items.item import Item


class Base(ABC):
    component_type: ComponentType

    in_degree:  int
    out_degree: int

    upstreams:   List["Base"]
    downstreams: List["Base"]

    pull_requests: List["Base"]
    pull_rr: int
    upstream_rr: int

    def __init__(self, comp_id: int) -> None:
        self.id = comp_id

        self.in_degree  = 0
        self.out_degree = 0
        self.upstreams   = []
        self.downstreams = []

        self.pull_requests = []
        self.pull_rr = 0
        self.upstream_rr = 0

    def add_link(self, component: "Base", link_type: LinkType):
        match link_type:
            case LinkType.INPUT:
                self.in_degree += 1
                self.upstreams.append(component)
            case LinkType.OUTPUT:
                self.out_degree += 1
                self.downstreams.append(component)
            case LinkType.NONE:
                return

    def add_pull(self, requester: "Base") -> None:
        self.pull_requests.append(requester)

    @abstractmethod
    def fulfill_requests(self) -> None:
        ...

    @abstractmethod
    def request_upstream(self) -> None:
        ...

    @abstractmethod
    def _accept_item(self, item: Item) -> bool:
        ...