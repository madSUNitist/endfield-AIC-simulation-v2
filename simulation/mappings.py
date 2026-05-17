"""Metadata and component factory mappings."""

from typing import Any, Dict, List, Literal, Tuple

from ._enums import ComponentType, LinkType, Direction, Rotation
from .units.base import Base

from .units import (
    DepotLoader, DepotUnloader, ProtocolStash,
    BeltBridge, Converger, Conveyor, ItemControlPort, Splitter,
)
from .utils import Vec, AreaCoverage, PathCoverage, Coverage

import json
from pathlib import Path

with open(Path("assets") / "unit_metadata.json") as metadata:
    MAPPING = json.load(metadata)

_DIR_MAP: dict[str, Direction] = {
    "up": Direction.UP, "down": Direction.DOWN,
    "left": Direction.LEFT, "right": Direction.RIGHT,
}


def get_metadata(component: ComponentType, **kwargs: Any) -> Tuple[Coverage, List[Tuple[LinkType, Vec, Direction]]]:
    """Return coverage footprint and port list for a component type.

    Conveyors use path-based metadata (PathCoverage + direction ports).
    Other types read from ``assets/unit_metadata.json``.
    """
    cov: Coverage
    if component is ComponentType.LOGISTICS_BELT_CONVEYOR:
        path = kwargs["path"]
        cov = PathCoverage(path)
        cells = cov.cells(Rotation.ROT_0)

        ports = [
            (LinkType.INPUT,  cells[0], _DIR_MAP[kwargs["direction_in"]]),
            (LinkType.OUTPUT, cells[-1], _DIR_MAP[kwargs["direction_out"]]),
        ]
        return cov, ports

    # ── Non-conveyor types ─────────────────────────────────
    meta: dict = {}
    match component:
        case ComponentType.DEPOT_ACCESS_DEPOT_LOADER:
            meta = MAPPING['depot-access']['depot-loader']
        case ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:
            meta = MAPPING['depot-access']['depot-unloader']
        case ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:
            meta = MAPPING['depot-access']['protocol-stash']
        case ComponentType.LOGISTICS_BELT_BELT_BRIDGE:
            meta = MAPPING['logistics-unit']['belt']['belt-bridge']
        case ComponentType.LOGISTICS_BELT_CONVERGER:
            meta = MAPPING['logistics-unit']['belt']['converger']
        case ComponentType.LOGISTICS_BELT_ITEM_CONTROL_PORT:
            meta = MAPPING['logistics-unit']['belt']['item-control-port']
        case ComponentType.LOGISTICS_BELT_SPLITTER:
            meta = MAPPING['logistics-unit']['belt']['splitter']
        case _:
            raise KeyError(component)

    cov = AreaCoverage(*meta['coverage'])
    ports = []
    for port in meta['ports']:
        pt = LinkType.INPUT if port['type'] == 'input' else LinkType.OUTPUT
        ports.append((pt, Vec(*port['offset']), _DIR_MAP[port['direction']]))
    return cov, ports


def get_components(component: ComponentType, comp_id: int, **cfg: object) -> Base:
    """Construct a component instance by type enum.

    Passes ``cfg`` kwargs to the component initialiser
    (e.g. ``length``, ``path`` for conveyors; ``id_gen``, ``inventory``
    for depot-access types).
    """
    match component:
        case ComponentType.DEPOT_ACCESS_DEPOT_LOADER:
            return DepotLoader(comp_id, **cfg)  # type: ignore[arg-type]
        case ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:
            return DepotUnloader(comp_id, **cfg)  # type: ignore[arg-type]
        case ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:
            return ProtocolStash(comp_id, **cfg)  # type: ignore[arg-type]
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
