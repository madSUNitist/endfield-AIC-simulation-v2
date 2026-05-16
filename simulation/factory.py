from typing import Any

from ._id_gen import IDGen
from ._enums import ComponentType as CT, Rotation as R
from .items.inventory import Inventory
from .utils import Vec
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
    "ROT_0": R.ROT_0,
    "ROT_1": R.ROT_1,
    "ROT_2": R.ROT_2,
    "ROT_3": R.ROT_3,
}


class Factory:
    def __init__(self, config: dict) -> None:
        self.id_gen = IDGen()
        self.inv = Inventory(50, self.id_gen,
                             defaults=config.get("inventory", {}))
        layout_dict, comp_configs = self._parse(config)
        self.layout = Layout(layout_dict)
        self.graph = Graph(self.layout, comp_configs=comp_configs)

    def _parse(self, config: dict
               ) -> tuple[dict[Vec, tuple[CT, R]], dict[Vec, dict[str, Any]]]:
        layout: dict[Vec, tuple[CT, R]] = {}
        cfgs: dict[Vec, dict[str, Any]] = {}
        for entry in config.get("components", []):
            pos = Vec(*entry["pos"])
            ct = _TYPE_MAP[entry["type"]]
            rot = _ROT_MAP.get(entry.get("rot", "ROT_0"), R.ROT_0)
            layout[pos] = (ct, rot)

            cfg: dict[str, Any] = {}
            if ct is CT.DEPOT_ACCESS_DEPOT_LOADER:
                cfg = {"id_gen": self.id_gen, "inventory": self.inv,
                       "item_type": entry["item"]}
            elif ct is CT.DEPOT_ACCESS_DEPOT_UNLOADER:
                cfg = {"id_gen": self.id_gen, "inventory": self.inv}
            elif ct is CT.LOGISTICS_BELT_CONVEYOR:
                cfg = {"length": entry.get("length", 4)}
            cfgs[pos] = cfg
        return layout, cfgs

    def tick(self) -> None:
        self.graph.tick()

    def run(self, ticks: int = 0) -> None:
        if not ticks:
            ticks = max(len(self.graph.order) * 2 + 10, 20)
        for _ in range(ticks):
            self.tick()
