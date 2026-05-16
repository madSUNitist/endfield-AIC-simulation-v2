from typing import Any, Optional
from pathlib import Path

from simulation.units.logistics_units.belt.conveyor import Conveyor


RENDER_MODES = ("id_type", "type", "id", "binary")


def render_item(item: Any | None, mode: str) -> str:
    if item is None:
        return " " if mode == "binary" else "  .  "
    if mode == "binary":
        return "1"
    t = str(item.type)[:6]
    s = str(item.id)
    if mode == "id_type":
        return f"{t}#{s}"
    if mode == "type":
        return t
    if mode == "id":
        return f"#{s}"
    return f"{t}#{s}"


def _pad(s: str, width: int) -> str:
    if len(s) >= width:
        return s[:width]
    return s.center(width)


def render_belt(conv: Conveyor, mode: str) -> str:
    width = 8 if mode in ("id_type",) else 6
    cells: list[str] = []
    for i in range(conv._length):
        idx = (conv._ptr - conv._count + conv._length + i) % conv._length
        cells.append(_pad(render_item(conv._slots[idx], mode), width))
    return "[" + " | ".join(cells) + "]"


def load_test_case(path: Path) -> dict:
    import json
    with path.open(encoding="utf-8") as f:
        return json.load(f)
