from enum import Enum, auto


class Direction(Enum):
    UP    = (0, +1)
    DOWN  = (0, -1)
    LEFT  = (+1, 0)
    RIGHT = (-1, 0)
    
    def __matmul__(self, other):
        from .utils import Vec
        new_direction = Vec(*self.value) @ other
        match new_direction.x, new_direction.y:
            case 0, 1:
                return Direction.UP
            case 0, -1:
                return Direction.DOWN
            case 1, 0:
                return Direction.LEFT
            case -1, 0:
                return Direction.RIGHT
            case _:
                raise KeyError(new_direction)

class Rotation(Enum):
    ROT_0 = auto()
    ROT_1 = auto()
    ROT_2 = auto()
    ROT_3 = auto()
    
    def __matmul__(self, other):
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
    INPUT = auto()
    OUTPUT = auto()
    NONE = auto()