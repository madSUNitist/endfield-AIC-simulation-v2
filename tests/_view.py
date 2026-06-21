from typing import Any, Optional
from pathlib import Path

from simulation.units.logistics_units.belt.conveyor import Conveyor
from simulation.units.logistics_units.belt.converger import Converger
from simulation.units.logistics_units.belt.splitter import Splitter
from simulation.units.depot_access.protocol_stash import ProtocolStash


RENDER_MODES = ("id_type", "type", "id", "binary")


def render_item(item: Any | None, mode: str) -> str:
    if item is None:
        return " " if mode == "binary" else "  .  "
    if mode == "binary":
        return "1"
    s = str(item.id)
    if mode == "id":
        return f"#{s}"
    t = str(item.type)[:4]
    if mode == "id_type":
        return f"{t}#{s}"
    if mode == "type":
        return t
    return f"{t}#{s}"


def _pad(s: str, width: int) -> str:
    if len(s) > width:
        return s[len(s) - width:]  # keep the rightmost part (ID number)
    return s.center(width)


def render_belt(conv: Conveyor, mode: str) -> str:
    width = 8 if mode in ("id_type",) else 6
    cells = [_pad(render_item(conv._slots[i], mode), width) for i in range(conv._length)]
    return "[" + " | ".join(cells) + "]"


def render_converger(conv: Converger, mode: str) -> str:
    width = 8 if mode in ("id_type",) else 6
    return "[" + _pad(render_item(conv._buffer, mode), width) + "]"


def render_splitter(comp: Splitter, mode: str) -> str:
    width = 8 if mode in ("id_type",) else 6
    return "[" + _pad(render_item(comp._buffer, mode), width) + "]"


def render_stash(comp: ProtocolStash, mode: str) -> str:
    width = 8 if mode in ("id_type",) else 6
    buf = _pad(render_item(comp._buffer, mode), width)
    cnt = comp._inv.count()
    return f"[{buf}|{cnt:>3d}]"


def load_test_case(path: Path) -> dict:
    import json5
    return json5.loads(path.read_text("utf-8"))
