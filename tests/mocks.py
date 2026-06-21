"""Shared mock classes for unit-mode tests."""

from simulation.items.item import Item
from simulation.units.logistics_units.belt.splitter import Splitter
from simulation.units.logistics_units.belt.converger import Converger
from simulation.units.logistics_units.belt.conveyor import Conveyor


class MockSink(Splitter):
    """Mock that accepts items and records received IDs."""

    def __init__(self, comp_id: int) -> None:
        """Initialise the sink with an empty received-ID log."""
        super().__init__(comp_id)
        self.received: list[int] = []

    def can_pull(self) -> bool:
        """Always claim to have an item available."""
        return True

    def fulfill_requests(self) -> None:
        """No-op — the sink never hands items downstream."""
        ...

    def request_upstream(self) -> None:
        """No-op — the sink never requests from upstream."""
        ...

    def _accept_item(self, item: Item) -> bool:
        """Record this sink's id and always accept the item."""
        self.received.append(self.id)
        return True


class MockSource(Converger):
    """Mock upstream that records pull requests."""

    def __init__(self, comp_id: int) -> None:
        """Initialise the source with a zero pull counter."""
        super().__init__(comp_id)
        self.pulls_received: int = 0

    def can_pull(self) -> bool:
        """Always claim to have an item available."""
        return True

    def fulfill_requests(self) -> None:
        """No-op — grants are observed via :meth:`add_pull` instead."""
        ...

    def request_upstream(self) -> None:
        """No-op — the source has no upstream of its own."""
        ...

    def add_pull(self, requester) -> None:  # type: ignore[override]
        """Count an incoming pull request instead of queuing it."""
        self.pulls_received += 1

    def _accept_item(self, item: Item) -> bool:
        """Reject all items — a source never accepts."""
        return False


class MockDownstream(Conveyor):
    """Mock downstream that accepts items and records received IDs."""

    def __init__(self, comp_id: int) -> None:
        """Initialise as a long conveyor with an empty received log."""
        super().__init__(comp_id, length=50)
        self.received_ids: list[int] = []

    def _accept_item(self, item: Item) -> bool:
        """Record this component's id, then delegate to the conveyor."""
        self.received_ids.append(self.id)
        return super()._accept_item(item)
