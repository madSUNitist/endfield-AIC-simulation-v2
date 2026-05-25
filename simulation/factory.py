"""Top-level factory that assembles a complete simulation from a config dict.

The Factory owns the ID generator, a shared global Inventory, a Layout
(grid occupancy), and a Graph (port connections + topological order).
"""

from typing import List

from ._id_gen import IDGen
from ._enums import ComponentType, Rotation
from .items.inventory import Inventory
from .items.itemstack import ItemStack
from .mappings import get_type, get_rotation
from .utils import Vec
from .utils.coverage import _expand
from .placement import Placement
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
        placements = self._parse(config)
        self.layout = Layout(placements)
        self.graph = Graph(self.layout)

    def _parse(self, config: dict) -> List[Placement]:
        """Parse a config dict into an ordered list of Placements.

        Args:
            config: Top-level config dict containing a ``"components"`` list.

        Returns:
            An ordered list of ``Placement`` records.  The order matches
            the ``"components"`` list in *config*.
        """
        placements: List[Placement] = []
        for entry in config.get("components", []):
            ct = get_type(entry["type"])
            rot = get_rotation(entry.get("rot", "ROT_0"))
            cfg: dict = {}

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

            if ct is ComponentType.DEPOT_ACCESS_DEPOT_LOADER:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = self.inv
                cfg["item_type"] = entry["item"]
            elif ct is ComponentType.DEPOT_ACCESS_DEPOT_UNLOADER:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = self.inv
            elif ct is ComponentType.DEPOT_ACCESS_PROTOCOL_STASH:
                cfg["id_gen"] = self.id_gen
                inv = Inventory(6, self.id_gen)
                if "stash_slots" in entry:
                    for i, slot in enumerate(entry["stash_slots"]):
                        if i >= 6:
                            break
                        inv._slots[i] = ItemStack(
                            slot["type"], self.id_gen,
                            capacity=50, count=slot["count"],
                        )
                cfg["inventory"] = inv

            placements.append(Placement(pos, ct, rot, cfg))

        return placements

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
