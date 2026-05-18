"""Top-level factory that assembles a complete simulation from a config dict.

The Factory owns the ID generator, a shared global Inventory, a Layout
(grid occupancy), and a Graph (port connections + topological order).
"""

from typing import Any

from ._id_gen import IDGen
from ._enums import ComponentType, Rotation
from .items.inventory import Inventory
from .mappings import get_type, get_rotation
from .utils import Vec
from .utils.coverage import _expand
from .layout import Layout
from .graph import Graph


class Factory(object):
    """Top-level assembler that builds a simulation from a JSON config.

    Owns the ID generator, a shared global Inventory, a Layout (grid
    occupancy), and a Graph (port connections + topological order).
    """

    def __init__(self, config: dict) -> None:
        """Parse config, build Layout + Graph.

        Args:
            config: Dict with top-level keys ``name``, ``ticks``,
                ``inventory`` (optional), ``components`` (list of
                component entries).
        """
        self.id_gen = IDGen()
        self.inv = Inventory(50, self.id_gen,
                             defaults=config.get("inventory", {}))
        layout_dict, comp_configs = self._parse(config)
        self.layout = Layout(layout_dict, comp_configs=comp_configs)
        self.graph = Graph(self.layout, comp_configs=comp_configs)

    def _parse(self, config: dict) -> tuple[dict[Vec, tuple[ComponentType, Rotation]], dict[Vec, dict[str, Any]]]:
        """Parse a config dict into layout and component-config maps.

        Args:
            config: Top-level config dict containing a ``"components"`` list.

        Returns:
            A tuple ``(layout, cfgs)`` where *layout* maps each component's
            origin to its ``(ComponentType, Rotation)`` and *cfgs* maps each
            origin to additional init kwargs.
        """
        layout: dict[Vec, tuple[ComponentType, Rotation]] = {}
        cfgs: dict[Vec, dict[str, Any]] = {}
        for entry in config.get("components", []):
            ct = get_type(entry["type"])
            rot = get_rotation(entry.get("rot", "ROT_0"))
            cfg: dict[str, Any] = {}

            if ct is ComponentType.LOGISTICS_BELT_CONVEYOR:
                path = entry.get("path")
                if not path or "direction_in" not in entry or "direction_out" not in entry:
                    raise ValueError(
                        f"conveyor entry must have 'path', 'direction_in', 'direction_out'; got {entry}"
                    )
                pos = Vec(*path[0])
                cells = _expand(path)
                cfg = {
                    "length": len(cells),
                    "path": path,
                    "direction_in": entry["direction_in"],
                    "direction_out": entry["direction_out"],
                }
            else:
                pos = Vec(*entry["pos"])

            layout[pos] = (ct, rot)

            if ct is ComponentType.DEPOT_ACCESS_DEPOT_LOADER:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = self.inv
                cfg["item_type"] = entry["item"]
            elif ct is ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = self.inv
            elif ct is ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = Inventory(6, self.id_gen)

            cfgs[pos] = cfg

        return layout, cfgs

    def tick(self) -> None:
        """Advance the simulation by one tick.

        Delegates to the underlying Graph's two-phase tick loop.
        """
        self.graph.tick()

    def run(self, ticks: int = 0) -> None:
        """Run multiple ticks.

        Args:
            ticks: Number of ticks to execute. If 0, a default is
                computed from the graph order length.
        """
        if not ticks:
            ticks = max(len(self.graph.order) * 2 + 10, 20)
        for _ in range(ticks):
            self.tick()
