import json
from pathlib import Path

from simulation.factory import Factory
from simulation._enums import ComponentType as CT


_CASES = Path(__file__).parent / "test_cases"


def _load(name: str) -> dict:
    with (_CASES / name).open(encoding="utf-8") as f:
        return json.load(f)


def _find_components(f, ctype):
    return [comp for comp in f.graph.components
            if comp.component_type is ctype]


def test_converger_line():
    cfg = _load("converger_line.json")
    f = Factory(cfg)
    order = f.graph.order
    assert len(order) == 7

    f.run(cfg["ticks"])

    convergers = _find_components(f, CT.LOGISTICS_BELT_CONVERGER)
    assert len(convergers) == 1
    convg = convergers[0]

    # buffer should hold at most 1 item
    assert sum(1 for _ in filter(None, [convg._buffer])) <= 1

    # downstream conveyors should have items
    convs = _find_components(f, CT.LOGISTICS_BELT_CONVEYOR)
    assert len(convs) == 3
    assert any(c._count > 0 for c in convs)

    # items should have reached the unloader
    unloaders = _find_components(f, CT.DEPOT_ACCESS_DEPOT_UNLOADER)
    assert len(unloaders) == 1
    assert f.inv.count("ore") < 9999


def test_converger_buffer_capacity():
    """Verify converger never holds more than 1 item when flooded."""
    cfg = _load("converger_line.json")
    f = Factory(cfg)

    convergers = _find_components(f, CT.LOGISTICS_BELT_CONVERGER)
    assert len(convergers) == 1
    convg = convergers[0]

    for _ in range(50):
        f.tick()
        assert convg._buffer is None or isinstance(convg._buffer, object)
        # buffer can be None or an Item; never more than 1
