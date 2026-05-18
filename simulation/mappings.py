"""Component metadata, factory functions, and lookup maps.

Provides the single-entry-point functions for constructing components
and resolving their grid metadata.  All internal maps are kept private;
callers use ``get_type`` / ``get_rotation`` / ``get_component`` /
``get_metadata`` instead.
"""

from typing import Any, Callable, Dict, List, Literal, Tuple

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

_METADATA_MAP: dict[ComponentType, tuple[str, ...]] = {
    ComponentType.DEPOT_ACCESS_DEPOT_LOADER:        ('depot-access', 'depot-loader'),
    ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:      ('depot-access', 'depot-unloader'),
    ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:      ('depot-access', 'protocol-stash'),
    ComponentType.LOGISTICS_BELT_BELT_BRIDGE:       ('logistics-unit', 'belt', 'belt-bridge'),
    ComponentType.LOGISTICS_BELT_CONVERGER:         ('logistics-unit', 'belt', 'converger'),
    ComponentType.LOGISTICS_BELT_ITEM_CONTROL_PORT: ('logistics-unit', 'belt', 'item-control-port'),
    ComponentType.LOGISTICS_BELT_SPLITTER:          ('logistics-unit', 'belt', 'splitter'),
}


def get_metadata(component: ComponentType, **kwargs: Any) -> Tuple[Coverage, List[Tuple[LinkType, Vec, Direction]]]:
    """Return coverage footprint and port list for a component type.

    Conveyors use path-based metadata (PathCoverage + direction ports).
    Other types read from ``assets/unit_metadata.json``.

    Args:
        component: The component type to look up.
        **kwargs: Must include ``path``, ``direction_in``, ``direction_out``
            when *component* is ``LOGISTICS_BELT_CONVEYOR``; ignored
            otherwise.

    Returns:
        A tuple of (coverage, ports) where *coverage* is a Coverage
        instance and *ports* is a list of (link_type, offset, direction).

    Raises:
        KeyError: If *component* is not recognised.
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
    meta: dict = MAPPING
    for key in _METADATA_MAP[component]:
        meta = meta[key]

    cov = AreaCoverage(*meta['coverage'])
    ports = []
    for port in meta['ports']:
        pt = LinkType.INPUT if port['type'] == 'input' else LinkType.OUTPUT
        ports.append((pt, Vec(*port['offset']), _DIR_MAP[port['direction']]))
    return cov, ports


_COMP_MAP: dict[ComponentType, Callable[..., Base]] = {
    ComponentType.DEPOT_ACCESS_DEPOT_LOADER:        DepotLoader,
    ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:      DepotUnloader,
    ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:      ProtocolStash,
    ComponentType.LOGISTICS_BELT_BELT_BRIDGE:       BeltBridge,
    ComponentType.LOGISTICS_BELT_CONVERGER:         Converger,
    ComponentType.LOGISTICS_BELT_CONVEYOR:          Conveyor,
    ComponentType.LOGISTICS_BELT_ITEM_CONTROL_PORT: ItemControlPort,
    ComponentType.LOGISTICS_BELT_SPLITTER:          Splitter,
}


def get_component(component: ComponentType, comp_id: int, **cfg: object) -> Base:
    """Construct a component instance by type enum.

    Passes ``cfg`` kwargs to the component initialiser
    (e.g. ``length``, ``path`` for conveyors; ``id_gen``, ``inventory``
    for depot-access types).

    Args:
        component: The component type to instantiate.
        comp_id: Unique identifier for the new component.
        **cfg: Additional keyword arguments forwarded to the constructor.

    Returns:
        A new component instance.

    Raises:
        KeyError: If *component* is not registered in the component map.
    """
    return _COMP_MAP[component](comp_id, **cfg)


_TYPE_MAP: dict[str, ComponentType] = {
    "depot_loader": ComponentType.DEPOT_ACCESS_DEPOT_LOADER,
    "depot_unloader": ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER,
    "protocol_stash": ComponentType.DEPOT_ACCESS_PROTOCOL_STASH,
    "conveyor": ComponentType.LOGISTICS_BELT_CONVEYOR,
    "splitter": ComponentType.LOGISTICS_BELT_SPLITTER,
    "converger": ComponentType.LOGISTICS_BELT_CONVERGER,
    "belt_bridge": ComponentType.LOGISTICS_BELT_BELT_BRIDGE,
    "item_control_port": ComponentType.LOGISTICS_BELT_ITEM_CONTROL_PORT,
}

_ROT_MAP: dict[str, Rotation] = {
    "ROT_0": Rotation.ROT_0, "ROT_1": Rotation.ROT_1,
    "ROT_2": Rotation.ROT_2, "ROT_3": Rotation.ROT_3,
}


def get_type(name: str) -> ComponentType:
    """Look up ComponentType by config string name.

    Args:
        name: Short name (e.g. ``"conveyor"``, ``"splitter"``).

    Returns:
        The matching ComponentType enum member.

    Raises:
        KeyError: If *name* is not recognised.
    """
    return _TYPE_MAP[name]


TYPE_NAMES: tuple[str, ...] = tuple(_TYPE_MAP.keys())


def get_type_name(component: ComponentType) -> str:
    """Return the config string name for a ComponentType.

    Args:
        component: The ComponentType enum member.

    Returns:
        The short string name (e.g. ``"conveyor"``, ``"splitter"``).

    Raises:
        KeyError: If *component* is not registered.
    """
    for name, ct in _TYPE_MAP.items():
        if ct is component:
            return name
    raise KeyError(component)


def get_rotation(name: str, default: Rotation = Rotation.ROT_0) -> Rotation:
    """Look up Rotation by config string name.

    Args:
        name: Rotation string (``"ROT_0"`` … ``"ROT_3"``).
        default: Fallback if *name* is not found. Defaults to ``ROT_0``.

    Returns:
        The matching Rotation enum member, or *default* if unknown.
    """
    return _ROT_MAP.get(name, default)