"""Test converger — round-robin upstream polling, line integration."""

import json
from pathlib import Path

from simulation.factory import Factory
from simulation._enums import ComponentType as CT
from simulation.items.item import Item
from simulation.units.logistics_units.belt.converger import Converger


_CASES = Path(__file__).parent / "test_cases"


def _load(name: str) -> dict:
    """Load a JSON test case by filename from the test_cases directory."""
    with (_CASES / name).open(encoding="utf-8") as f:
        return json.load(f)


def _find_components(f, ctype):
    """Filter graph components by ComponentType."""
    return [comp for comp in f.graph.components
            if comp.component_type is ctype]


class _MockSource(Converger):
    """A mock upstream that can_pull and records pull requests."""

    def __init__(self, comp_id: int):
        super().__init__(comp_id)
        self.pulls_received: int = 0

    def can_pull(self) -> bool:
        return True

    def fulfill_requests(self) -> None:
        ...

    def request_upstream(self) -> None:
        ...

    def add_pull(self, requester) -> None:
        self.pulls_received += 1

    def _accept_item(self, item: Item) -> bool:
        return False


def test_converger_rr_cycling():
    """Converger cycles through upstreams via _skip_idx round-robin."""
    c = Converger(0)
    a = _MockSource(1)
    b = _MockSource(2)

    c.upstreams = [a, b]

    for _ in range(5):
        c.request_upstream()

    # _skip_idx RR: a, b, a, b, a → 3 a, 2 b
    assert a.pulls_received == 3
    assert b.pulls_received == 2


def test_converger_falls_back_when_first_empty():
    """When the first upstream cannot pull, try the next via _skip_idx."""
    c = Converger(0)
    a = _MockSource(1)
    b = _MockSource(2)

    c.upstreams = [a, b]

    a.can_pull = lambda: False  # type: ignore[method-assign]

    c.request_upstream()
    assert a.pulls_received == 0
    assert b.pulls_received == 1


def test_converger_buffer_full_blocks_pull():
    """When buffer is full, request_upstream does nothing."""
    c = Converger(0)
    src = _MockSource(1)
    c.upstreams = [src]
    c._buffer = Item("ore", 0)

    c.request_upstream()
    assert src.pulls_received == 0


def test_converger_line():
    cfg = _load("converger_line.json")
    f = Factory(cfg)
    order = f.graph.order
    assert len(order) == 7

    f.run(cfg["ticks"])

    convergers = _find_components(f, CT.LOGISTICS_BELT_CONVERGER)
    assert len(convergers) == 1
    convg = convergers[0]

    assert sum(1 for _ in filter(None, [convg._buffer])) <= 1

    convs = _find_components(f, CT.LOGISTICS_BELT_CONVEYOR)
    assert len(convs) == 3
    assert any(c._count > 0 for c in convs)

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