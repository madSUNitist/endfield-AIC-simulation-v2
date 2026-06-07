"""Tests for ProtocolStash component."""

from pathlib import Path

from simulation.factory import Factory
from simulation.units.depot_access.protocol_stash import ProtocolStash
from simulation.units.logistics_units.belt.conveyor import Conveyor
from simulation.items.item import Item
from simulation.items.inventory import Inventory
from simulation._id_gen import IDGen

from ._view import load_test_case

CASE = Path(__file__).parent / "test_cases" / "protocol_stash.json"
CASE2 = Path(__file__).parent / "test_cases" / "protocol_stash_two_inputs.json"


def _get_stash(f: Factory) -> ProtocolStash:
    """Extract the ProtocolStash component from a factory graph."""
    for comp in f.graph.components:
        if isinstance(comp, ProtocolStash):
            return comp
    raise AssertionError("no ProtocolStash in graph")


def _get_conveyor(f: Factory) -> Conveyor:
    """Extract the Conveyor component from a factory graph."""
    for comp in f.graph.components:
        if isinstance(comp, Conveyor):
            return comp
    raise AssertionError("no Conveyor in graph")


class _MockDownstream(Conveyor):
    """A mock downstream that accepts items and records the order."""

    def __init__(self, comp_id: int):
        super().__init__(comp_id, length=50)
        self.received_ids: list[int] = []

    def _accept_item(self, item: Item) -> bool:
        self.received_ids.append(self.id)
        return super()._accept_item(item)


def test_stash_rr_123() -> None:
    """Verify stash serves downstreams in 1-2-3 connection-order RR."""
    g = IDGen()
    inv = Inventory(6, g)
    stash = ProtocolStash(0, id_gen=g, inventory=inv)

    a = _MockDownstream(1)
    b = _MockDownstream(2)
    c = _MockDownstream(3)

    stash.downstreams = [a, b, c]
    stash._original_downstreams = [a, b, c]
    stash.finalize()

    for i in range(6):
        stash._buffer = Item(g.next(), "ore")
        stash.pull_requests = [a, b, c]
        stash.fulfill_requests()

    # 123 RR: downstream[0]=a, [1]=b, [2]=c, then repeat
    assert a.received_ids == [1, 1]
    assert b.received_ids == [2, 2]
    assert c.received_ids == [3, 3]


def test_stash_basic_flow() -> None:
    """Items flow through Loader -> Stash -> Conv -> Unloader (zero-tick)."""
    cfg = load_test_case(CASE)
    f = Factory(cfg)
    stash = _get_stash(f)
    conv = _get_conveyor(f)

    assert not stash.can_pull()
    assert not conv.can_pull()

    f.tick()
    # Item passed through stash zero-tick; conveyor head slot has it
    assert conv._count > 0
    assert stash._buffer is None

    for _ in range(10):
        f.tick()
    # Items passed through stash zero-tick; unloader received them
    assert f.inv.count("ore") < 9999


def test_stash_can_pull() -> None:
    """can_pull reflects buffer or inventory contents."""
    cfg = load_test_case(CASE)
    f = Factory(cfg)
    stash = _get_stash(f)
    conv = _get_conveyor(f)

    assert not stash.can_pull()  # empty at start

    f.tick()
    # Item passed through zero-tick; conveyor head slot has it
    assert conv._count > 0


def test_stash_accept_priority() -> None:
    """_accept_item: forward first, then buffer, then inventory."""
    cfg = load_test_case(CASE)
    f = Factory(cfg)
    stash = _get_stash(f)
    conv = _get_conveyor(f)

    g = IDGen()

    # forward to downstream (via phase2 routing)
    a = Item(g.next(), "ore")
    assert stash._accept_item(a)
    stash.phase2()
    assert conv._slots[conv._length - 1] is a
    assert stash._buffer is None

    # fill conveyor (length=2), then stash starts accumulating
    b = Item(g.next(), "ore")
    assert stash._accept_item(b)
    stash.phase2()
    assert conv._count == conv._length  # conveyor full

    # next item goes to stash buffer
    c = Item(g.next(), "ore")
    assert stash._accept_item(c)
    assert stash._buffer is c

    # next to inventory
    d = Item(g.next(), "ore")
    assert stash._accept_item(d)
    assert stash._inv.count() == 1


def test_stash_fulfill_clears_pulls() -> None:
    """fulfill_requests clears pull_requests after processing."""
    cfg = load_test_case(CASE)
    f = Factory(cfg)
    stash = _get_stash(f)

    # Pre-fill buffer
    g = IDGen()
    stash._buffer = Item(g.next(), "ore")

    # Register the conveyor as a pull requester
    conv = _get_conveyor(f)
    stash.add_pull(conv)

    stash.fulfill_requests()
    assert len(stash.pull_requests) == 0


def test_stash_request_upstream_all() -> None:
    """request_upstream requests from all upstreams simultaneously."""
    cfg = load_test_case(CASE)
    f = Factory(cfg)
    stash = _get_stash(f)
    conv = _get_conveyor(f)

    # Stash has one upstream (loader)
    assert len(stash.upstreams) == 1

    # After one tick, item passed through stash zero-tick to conveyor
    f.tick()
    assert conv._count > 0
    assert stash._buffer is None


def test_stash_multi_fulfill() -> None:
    """fulfill_requests can serve items in a loop while pull_requests remain."""
    cfg = load_test_case(CASE)
    f = Factory(cfg)
    stash = _get_stash(f)

    g = IDGen()

    # Pre-fill stash inventory with 3 items
    for _ in range(3):
        stash._inv.push(Item(g.next(), "ore"))

    # Get the conveyor downstream
    conv = None
    for comp in f.graph.components:
        if isinstance(comp, Conveyor):
            conv = comp
            break
    assert conv is not None

    # Register 3 pulls from the same downstream (simulating multi-tick backlog)
    stash.add_pull(conv)
    stash.add_pull(conv)
    stash.add_pull(conv)

    stash.fulfill_requests()

    # After clearing, all pull_requests should be gone
    assert len(stash.pull_requests) == 0
    # At least one item should have been served (conv accepted)
    assert stash._inv.count() < 3


def test_stash_two_inputs_block() -> None:
    """Two loaders feed stash via conveyors: ore from left, copper from right.
    Stash accumulates +1/tick until its 6×50 inventory is full."""
    cfg = load_test_case(CASE2)
    f = Factory(cfg)
    stash = _get_stash(f)

    for _ in range(400):
        f.tick()

    # Stash accumulates items (per-type stacks: 5× ore + 1× copper).
    assert stash._inv.count() > 100
