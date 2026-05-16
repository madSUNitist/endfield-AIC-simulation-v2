from ._enums import ComponentType
from .units.base import Base

from .units import (
    DepotLoader, 
    DepotUnloader, 
    ProtocolStash, 
    
    BeltBridge, 
    Converger, 
    Conveyor, 
    ItemControlPort, 
    Splitter
)

from typing import Dict, List, Literal, Tuple
from ._enums import LinkType, Direction
from .utils import Vec, Area

import json
from pathlib import Path

with open(Path("assets") / "unit_metadata.json") as metadata:
    MAPPING = json.load(metadata)

def get_metadata(component: ComponentType) -> Tuple[Area, List[Tuple[LinkType, Vec, Direction]]]:
    match component:
        case ComponentType.DEPOT_ACCESS_DEPOT_LOADER:
            metadata = MAPPING['depot-access']['depot-loader']
        case ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:
            metadata = MAPPING['depot-access']['depot-unloader']
        case ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:
            metadata = MAPPING['depot-access']['protocol-stash']

        case ComponentType.LOGISTICS_BELT_BELT_BRIDGE:
            metadata = MAPPING['logistics-unit']['belt']['belt-bridge']
        case ComponentType.LOGISTICS_BELT_CONVERGER:
            metadata = MAPPING['logistics-unit']['belt']['converger']
        case ComponentType.LOGISTICS_BELT_CONVEYOR:
            metadata = MAPPING['logistics-unit']['belt']['conveyor']
        case ComponentType.LOGISTICS_BELT_ITEM_CONTROL_PORT:
            metadata = MAPPING['logistics-unit']['belt']['item-control-port']
        case ComponentType.LOGISTICS_BELT_SPLITTER:
            metadata = MAPPING['logistics-unit']['belt']['splitter']
    
        case _:
            raise KeyError(component)

    area = Area(*metadata['coverage'])
    ports = []
    for port in metadata['ports']:
        match port['type']:
            case 'input':
                port_type = LinkType.INPUT
            case 'output':
                port_type = LinkType.OUTPUT
            case _:
                raise KeyError(port['type'])
        
        offset_vec = Vec(*port['offset']) 
        
        match port['direction']:
            case 'up':
                direction = Direction.UP
            case 'down':
                direction = Direction.DOWN
            case 'left':
                direction = Direction.LEFT
            case 'right':
                direction = Direction.RIGHT
            case _:
                raise KeyError(port['direction'])
        
        ports.append((port_type, offset_vec, direction))
    
    return area, ports

def get_components(component: ComponentType, comp_id: int, **cfg: object) -> Base:
    match component:
        case ComponentType.DEPOT_ACCESS_DEPOT_LOADER:
            return DepotLoader(comp_id, **cfg)  # type: ignore[arg-type]
        case ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:
            return DepotUnloader(comp_id, **cfg)  # type: ignore[arg-type]
        case ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:
            return ProtocolStash(comp_id)

        case ComponentType.LOGISTICS_BELT_BELT_BRIDGE:
            return BeltBridge(comp_id)
        case ComponentType.LOGISTICS_BELT_CONVERGER:
            return Converger(comp_id)
        case ComponentType.LOGISTICS_BELT_CONVEYOR:
            return Conveyor(comp_id, **cfg)  # type: ignore[arg-type]
        case ComponentType.LOGISTICS_BELT_ITEM_CONTROL_PORT:
            return ItemControlPort(comp_id)
        case ComponentType.LOGISTICS_BELT_SPLITTER:
            return Splitter(comp_id)
    
    raise KeyError(component)