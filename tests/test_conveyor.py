import json
from pathlib import Path

from simulation.factory import Factory
from simulation._enums import ComponentType as CT


_CASES = Path(__file__).parent / "test_cases"


def _load(name: str) -> dict:
    with (_CASES / name).open(encoding="utf-8") as f:
        return json.load(f)


def _find_conveyors(f):
    return [comp for comp in f.graph.components.values()
            if comp.component_type is CT.LOGISTICS_BELT_CONVEYOR]


def test_belt_line():
    cfg = _load("belt_line.json")
    f = Factory(cfg)
    assert len(f.graph.order) == 3
    f.run(cfg["ticks"])
    convs = _find_conveyors(f)
    assert len(convs) == 1
    # conveyor buffer should have items (they flowed)
    conv = convs[0]
    assert conv._count > 0


def test_belt_accumulate():
    cfg = _load("belt_accumulate.json")
    f = Factory(cfg)
    assert len(f.graph.order) == 3
    f.run(cfg["ticks"])
    convs = _find_conveyors(f)
    assert len(convs) == 1
    assert convs[0]._count > 0


def test_loader_unloader():
    cfg = _load("loader_unloader.json")
    f = Factory(cfg)
    assert len(f.graph.order) == 3
    f.run(cfg["ticks"])
    # items should have flowed from loader through conveyor to unloader
    convs = _find_conveyors(f)
    assert len(convs) == 1
    assert convs[0]._count > 0


def test_all_json_load():
    for j in sorted(_CASES.glob("*.json")):
        with j.open(encoding="utf-8") as f:
            cfg = json.load(f)
        f = Factory(cfg)
        f.run(cfg.get("ticks", 30))
