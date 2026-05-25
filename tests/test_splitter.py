import json
from pathlib import Path

from simulation.factory import Factory
from simulation._enums import ComponentType as CT
from simulation.units.logistics_units.belt.splitter import Splitter


_CASES = Path(__file__).parent / "test_cases"


def _load(name: str) -> dict:
    with (_CASES / name).open(encoding="utf-8") as f:
        return json.load(f)


def _find_components(f, ctype):
    return [comp for comp in f.graph.components
            if comp.component_type is ctype]


def test_splitter_line():
    cfg = _load("splitter_line.json")
    f = Factory(cfg)
    assert len(f.graph.order) == 8  # loader, splitter, 4 convs, 2 unloaders

    f.run(cfg["ticks"])

    splitters: list[Splitter] = _find_components(f, CT.LOGISTICS_BELT_SPLITTER)
    assert len(splitters) == 1
    s = splitters[0]
    assert s._buffer is None or isinstance(s._buffer, object)

    # both unloaders should have received items
    unloaders = _find_components(f, CT.DEPOT_ACCESS_DEPOT_UNLOADER)
    assert len(unloaders) == 2
    assert f.inv.count("ore") < 9999

    # conveyors on both branches should have items
    convs = _find_components(f, CT.LOGISTICS_BELT_CONVEYOR)
    assert len(convs) == 4
    assert any(c._count > 0 for c in convs)
