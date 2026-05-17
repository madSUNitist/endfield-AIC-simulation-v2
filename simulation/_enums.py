"""Enumerations for component types, directions, rotations, and link types."""

from enum import Enum, auto


class Direction(Enum):
    """Cardinal directions in the simulation grid, aligned with screen coordinates.

    In this convention +x is right, +y is down, matching Canvas pixel space.
    This eliminates y-flip in the renderer and makes all coordinate math consistent.

    Attributes:
        UP: (0, -1) — negative y direction.
        DOWN: (0, +1) — positive y direction.
        LEFT: (-1, 0) — negative x direction.
        RIGHT: (+1, 0) — positive x direction.
    """
    UP    = (0, -1)
    DOWN  = (0, +1)
    LEFT  = (-1, 0)
    RIGHT = (+1, 0)

    def __matmul__(self, other):
        """Rotate this direction by a Rotation."""
        from .utils import Vec
        new_direction = Vec(*self.value) @ other
        match new_direction.x, new_direction.y:
            case 0, -1:
                return Direction.UP
            case 0, 1:
                return Direction.DOWN
            case -1, 0:
                return Direction.LEFT
            case 1, 0:
                return Direction.RIGHT
            case _:
                raise KeyError(new_direction)

class Rotation(Enum):
    """Clockwise rotations in 90-degree increments.

    Attributes:
        ROT_0: No rotation (0°).
        ROT_1: 90° clockwise.
        ROT_2: 180° clockwise.
        ROT_3: 270° clockwise.
    """
    ROT_0 = auto()
    ROT_1 = auto()
    ROT_2 = auto()
    ROT_3 = auto()
    
    def __matmul__(self, other):
        """Compose two rotations.

        Args:
            other: Another Rotation to compose with.

        Returns:
            The resulting Rotation after composition.
        """
        match (self.value, other):
            case Rotation.ROT_0, _:
                return other
            case _, Rotation.ROT_0:
                return self
            case Rotation.ROT_1, Rotation.ROT_1:
                return Rotation.ROT_2
            case Rotation.ROT_1, Rotation.ROT_2:
                return Rotation.ROT_3
            case Rotation.ROT_1, Rotation.ROT_3:
                return Rotation.ROT_0
            case Rotation.ROT_2, Rotation.ROT_1:
                return Rotation.ROT_3
            case Rotation.ROT_2, Rotation.ROT_2:
                return Rotation.ROT_0
            case Rotation.ROT_2, Rotation.ROT_3:
                return Rotation.ROT_1
            case Rotation.ROT_3, Rotation.ROT_1:
                return Rotation.ROT_0
            case Rotation.ROT_3, Rotation.ROT_2:
                return Rotation.ROT_1
            case Rotation.ROT_3, Rotation.ROT_3:
                return Rotation.ROT_2

class ComponentType(Enum):
    """All supported component types in the simulation.

    Attributes are organized by category: depot access, logistics belts,
    logistics pipes, power units, and production units.
    """
    # Depot Access
    DEPOT_ACCESS_CONDUIT_INLET_MANIFOLD = auto()
    DEPOT_ACCESS_CONDUIT_INLET = auto()
    DEPOT_ACCESS_CONDUIT_OUTLET_MANIFOLD = auto()
    DEPOT_ACCESS_CONDUIT_OUTLET = auto()
    DEPOT_ACCESS_DEPOT_LOADER = auto()
    DEPOT_ACCESS_DEPOT_UNLOADER = auto()
    DEPOT_ACCESS_FLUID_TANK = auto()
    DEPOT_ACCESS_PROTOCOL_STASH = auto()

    # Logistics Units - Belt
    LOGISTICS_BELT_BELT_BRIDGE = auto()
    LOGISTICS_BELT_CONVERGER = auto()
    LOGISTICS_BELT_CONVEYOR = auto()
    LOGISTICS_BELT_ITEM_CONTROL_PORT = auto()
    LOGISTICS_BELT_SPLITTER = auto()

    # Logistics Units - Pipe
    LOGISTICS_PIPE_PIPE_BRIDGE = auto()
    LOGISTICS_PIPE_PIPE_CONTROL_PORT = auto()
    LOGISTICS_PIPE_PIPE_CONVERGER = auto()
    LOGISTICS_PIPE_PIPE_SPLITTER = auto()
    LOGISTICS_PIPE_PIPE = auto()

    # Power Unit
    POWER_UNIT_THERMAL_BANK = auto()

    # Production Unit
    PRODUCTION_UNIT_EXPANDED_CRUCIBLE = auto()
    PRODUCTION_UNIT_FILLING_UNIT = auto()
    PRODUCTION_UNIT_FITTING_UNIT = auto()
    PRODUCTION_UNIT_FORGE_OF_THE_SKY = auto()
    PRODUCTION_UNIT_GEARING_UNIT = auto()
    PRODUCTION_UNIT_GRINDING_UNIT = auto()
    PRODUCTION_UNIT_MOULDING_UNIT = auto()
    PRODUCTION_UNIT_PACKAGING_UNIT = auto()
    PRODUCTION_UNIT_PLANTING_UNIT = auto()
    PRODUCTION_UNIT_PURIFICATION_UNIT = auto()
    PRODUCTION_UNIT_REACTOR_CRUCIBLE = auto()
    PRODUCTION_UNIT_REFINING_UNIT = auto()
    PRODUCTION_UNIT_SEED_PICKING_UNIT = auto()
    PRODUCTION_UNIT_SHREDDING_UNIT = auto()
    PRODUCTION_UNIT_WATER_TREATMENT_UNIT = auto()

class LinkType(Enum):
    """Port link direction for component connections.

    Attributes:
        INPUT: Port that receives items/resources.
        OUTPUT: Port that sends items/resources.
        NONE: No connection (unused port).
    """
    INPUT = auto()
    OUTPUT = auto()
    NONE = auto()