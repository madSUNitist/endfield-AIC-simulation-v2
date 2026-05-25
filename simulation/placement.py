"""Component placement descriptor for the simulation grid.

A Placement binds a component type, its position, rotation, and
extra configuration into a single object consumed by Layout and Graph.
"""

from dataclasses import dataclass
from typing import Any, Dict

from .utils import Vec
from ._enums import ComponentType, Rotation


@dataclass
class Placement:
    """A single component placed on the grid.

    Attributes:
        pos: Grid coordinate of the component origin.
        component_type: The type of component (conveyor, splitter, …).
        rotation: Orientation on the grid (ROT_0 … ROT_3).
        config: Extra type-specific settings, e.g. *path*, *direction_in*,
            *direction_out* for conveyors, or *item* for depot_loader.
    """

    pos: Vec
    component_type: ComponentType
    rotation: Rotation
    config: Dict[str, Any]