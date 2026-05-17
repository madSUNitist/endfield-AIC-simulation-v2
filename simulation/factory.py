"""Top-level factory that assembles a complete simulation from a config dict."""

from typing import Any

from ._id_gen import IDGen
from ._enums import ComponentType as CT, Rotation as R
from .items.inventory import Inventory
from .utils import Vec
from .utils.coverage import _expand
from .layout import Layout
from .graph import Graph


_TYPE_MAP: dict[str, CT] = {
    "depot_loader": CT.DEPOT_ACCESS_DEPOT_LOADER,
    "depot_unloader": CT.DEPOT_ACCESS_DEPOT_UNLOADER,
    "protocol_stash": CT.DEPOT_ACCESS_PROTOCOL_STASH,
    "conveyor": CT.LOGISTICS_BELT_CONVEYOR,
    "splitter": CT.LOGISTICS_BELT_SPLITTER,
    "converger": CT.LOGISTICS_BELT_CONVERGER,
    "belt_bridge": CT.LOGISTICS_BELT_BELT_BRIDGE,
    "item_control_port": CT.LOGISTICS_BELT_ITEM_CONTROL_PORT,
}

_ROT_MAP: dict[str, R] = {
    "ROT_0": R.ROT_0, "ROT_1": R.ROT_1,
    "ROT_2": R.ROT_2, "ROT_3": R.ROT_3,
}


class Factory:
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

    def _parse(self, config: dict
               ) -> tuple[dict[Vec, tuple[CT, R]], dict[Vec, dict[str, Any]]]:
        layout: dict[Vec, tuple[CT, R]] = {}
        cfgs: dict[Vec, dict[str, Any]] = {}
        for entry in config.get("components", []):
            ct = _TYPE_MAP[entry["type"]]
            rot = _ROT_MAP.get(entry.get("rot", "ROT_0"), R.ROT_0)
            cfg: dict[str, Any] = {}

            if ct is CT.LOGISTICS_BELT_CONVEYOR:
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

            if ct is CT.DEPOT_ACCESS_DEPOT_LOADER:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = self.inv
                cfg["item_type"] = entry["item"]
            elif ct is CT.DEPOT_ACCESS_DEPOT_UNLOADER:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = self.inv
            elif ct is CT.DEPOT_ACCESS_PROTOCOL_STASH:
                cfg["id_gen"] = self.id_gen
                cfg["inventory"] = Inventory(6, self.id_gen)

            cfgs[pos] = cfg

        return layout, cfgs

    def tick(self) -> None:
        """Advance the simulation by one tick (delegates to Graph)."""
        self.graph.tick()

    def run(self, ticks: int = 0) -> None:
        """Run multiple ticks.

        If ``ticks`` is 0, runs a default number of ticks based on
        graph order length.
        """
        if not ticks:
            ticks = max(len(self.graph.order) * 2 + 10, 20)
        for _ in range(ticks):
            self.tick()
