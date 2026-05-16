from typing import List

from .._enums import LinkType, ComponentType


class Base(object):
    component_type: ComponentType
    
    in_degree:  int
    out_degree: int
    
    upstreams:   List["Base"]
    downstreams: List["Base"]
    
    def __init__(self, comp_id: int) -> None:
        self.id = comp_id
        
        self.in_degree  = 0
        self.out_degree = 0
        self.upstreams   = []
        self.downstreams = []
    
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
    
    def _request(self):
        pass