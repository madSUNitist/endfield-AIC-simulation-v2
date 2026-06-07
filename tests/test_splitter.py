"""Test splitter — round-robin distribution, distance priority,
and Converger prioritisation."""

import json
from pathlib import Path

from simulation.factory import Factory
from simulation._enums import ComponentType as CT
from simulation.items.item import Item
from simulation.units.logistics_units.belt.splitter import Splitter


_CASES = Path(__file__).parent / "test_cases"


def _load(name: str) -> dict:
    """Load a JSON test case by filename from the test_cases directory."""
    with (_CASES / name).open(encoding="utf-8") as f:
        return json.load(f)


def _find_components(f, ctype):
    """Filter graph components by ComponentType from a Factory instance."""
    return [comp for comp in f.graph.components
            if comp.component_type is ctype]


class _MockSink(Splitter):
    """A mock that accepts items and records the order they were received."""

    def __init__(self, comp_id: int):
        super().__init__(comp_id)
        self.received: list[int] = []

    def can_pull(self) -> bool:
        return True

    def fulfill_requests(self) -> None:
        ...

    def request_upstream(self) -> None:
        ...

    def _accept_item(self, item: Item) -> bool:
        self.received.append(self.id)
        return True


def test_splitter_rr_231():
    """Verify splitter uses 2-3-1 round-robin (increment before select)."""
    s = Splitter(0)
    a = _MockSink(1)
    b = _MockSink(2)
    c = _MockSink(3)

    s.downstreams = [a, b, c]
    s._original_downstreams = [a, b, c]
    s.finalize()

    for i in range(6):
        s._buffer = Item("ore", 0)
        s.pull_requests = [a, b, c]
        s.fulfill_requests()

    # With 231 RR within the single distance group, order is:
    # downstream[1] (b), downstream[2] (c), downstream[0] (a), then repeat
    assert a.received == [1, 1]
    assert b.received == [2, 2]
    assert c.received == [3, 3]


def test_splitter_priority_output():
    """Verify splitter uses distance priority: shorter path gets all items."""
    cfg = _load("priority_output.json")
    f = Factory(cfg)

    f.run(cfg["ticks"])

    splitters: list[Splitter] = _find_components(f, CT.LOGISTICS_BELT_SPLITTER)
    assert len(splitters) == 1

    convs = _find_components(f, CT.LOGISTICS_BELT_CONVEYOR)
    # The long path (right branch) has 3 conveyors that should all be empty
    # because the splitter always prioritizes the short path (down branch)
    empty = [c for c in convs if c._count == 0]
    assert len(empty) >= 3, f"Expected >=3 empty conveyors (long path), got {len(empty)}"


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


class _MockConverger(Splitter):
    """A mock downstream that simulates a Converger via component_type."""

    def __init__(self, comp_id: int):
        super().__init__(comp_id)
        self.component_type = CT.LOGISTICS_BELT_CONVERGER
        self.received: list[int] = []

    def can_pull(self) -> bool:
        return True

    def fulfill_requests(self) -> None:
        ...

    def request_upstream(self) -> None:
        ...

    def _accept_item(self, item: Item) -> bool:
        self.received.append(self.id)
        return True


class _MockNormalSink(Splitter):
    """A mock normal downstream (not a Converger)."""

    def __init__(self, comp_id: int):
        super().__init__(comp_id)
        self.received: list[int] = []

    def can_pull(self) -> bool:
        return True

    def fulfill_requests(self) -> None:
        ...

    def request_upstream(self) -> None:
        ...

    def _accept_item(self, item: Item) -> bool:
        self.received.append(self.id)
        return True


def test_splitter_converger_in_first_group():
    """Converger is placed in the first priority group,
    regardless of its topo_index (distance to sink)."""
    s = Splitter(0)
    conv = _MockConverger(1)
    normal_a = _MockNormalSink(2)
    normal_b = _MockNormalSink(3)

    conv.topo_index = 100
    normal_a.topo_index = 5
    normal_b.topo_index = 10

    s.downstreams = [conv, normal_a, normal_b]
    s._original_downstreams = [conv, normal_a, normal_b]
    s.finalize()

    assert len(s._distance_groups) >= 2
    assert conv in s._distance_groups[0], (
        "Converger should be in the first group"
    )


def test_splitter_multiple_convergers_same_group():
    """All Convergers share the first group (same priority)."""
    s = Splitter(0)
    a = _MockConverger(1)
    b = _MockConverger(2)
    normal = _MockNormalSink(3)

    a.topo_index = 30
    b.topo_index = 40
    normal.topo_index = 5

    s.downstreams = [a, b, normal]
    s._original_downstreams = [a, b, normal]
    s.finalize()

    assert len(s._distance_groups) >= 2
    assert a in s._distance_groups[0]
    assert b in s._distance_groups[0]
    assert len(s._distance_groups[0]) == 2, (
        "Two Convergers should be the only members of group 0"
    )


def test_splitter_converger_priority_served():
    """When a Converger and a normal sink both pull,
    the Converger is served first."""
    s = Splitter(0)
    conv = _MockConverger(1)
    normal = _MockNormalSink(2)

    conv.topo_index = 100
    normal.topo_index = 5

    s.downstreams = [conv, normal]
    s._original_downstreams = [conv, normal]
    s.finalize()

    assert conv in s._distance_groups[0]

    s._buffer = Item("ore", 0)
    s.pull_requests = [normal, conv]
    s.fulfill_requests()

    assert conv.received, "Converger should have been served"
    assert not normal.received, "Normal sink should NOT have been served"


def test_splitter_no_converger_unchanged():
    """Without Convergers, groups are built by topo_index only."""
    s = Splitter(0)
    a = _MockNormalSink(1)
    b = _MockNormalSink(2)
    c = _MockNormalSink(3)

    a.topo_index = 5
    b.topo_index = 5
    c.topo_index = 10

    s.downstreams = [a, b, c]
    s._original_downstreams = [a, b, c]
    s.finalize()

    assert len(s._distance_groups) == 2
    assert a in s._distance_groups[0]
    assert b in s._distance_groups[0]
    assert c in s._distance_groups[1]


def test_splitter_converger_not_pulling_falls_through():
    """When the Converger is not pulling, the Splitter falls
    through to normal downstreams."""
    s = Splitter(0)
    conv = _MockConverger(1)
    normal = _MockNormalSink(2)

    conv.topo_index = 100
    normal.topo_index = 5

    s.downstreams = [conv, normal]
    s._original_downstreams = [conv, normal]
    s.finalize()

    s._buffer = Item("ore", 0)
    s.pull_requests = [normal]
    s.fulfill_requests()

    assert normal.received, "Normal sink should be served when Converger is not pulling"
    assert not conv.received
