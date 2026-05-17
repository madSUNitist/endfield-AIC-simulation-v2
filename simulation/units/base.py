"""Abstract base class for all simulation components.

Each component maintains upstream/downstream links and a round-robin
pull system for item transfer.
"""

from abc import ABC, abstractmethod
from typing import List

from .._enums import LinkType, ComponentType
from ..items.item import Item


class Base(ABC):
    """Abstract base for a simulation unit with links and pull-request logic."""

    component_type: ComponentType

    in_degree:  int
    out_degree: int

    upstreams:   List["Base"]
    downstreams: List["Base"]

    pull_requests: List["Base"]
    pull_rr: int
    upstream_rr: int

    def __init__(self, comp_id: int) -> None:
        """Args:
            comp_id: Unique numeric identifier for this component.
        """
        self.id = comp_id

        self.in_degree  = 0
        self.out_degree = 0
        self.upstreams   = []
        self.downstreams = []

        self.pull_requests = []
        self.pull_rr = 0
        self.upstream_rr = 0

    def add_link(self, component: "Base", link_type: LinkType):
        """Register a link to another component.

        Args:
            component: The component to link.
            link_type: Whether the link is INPUT, OUTPUT, or NONE.
        """
        match link_type:
            case LinkType.INPUT:
                self.in_degree += 1
                self.upstreams.append(component)
            case LinkType.OUTPUT:
                self.out_degree += 1
                self.downstreams.append(component)
            case LinkType.NONE:
                return

    def add_pull(self, requester: "Base") -> None:
        """Add a downstream component to the pull-request queue.

        Args:
            requester: The component requesting an item pull.
        """
        self.pull_requests.append(requester)

    @abstractmethod
    def fulfill_requests(self) -> None:
        """Fulfill pending pull requests by transferring items downstream."""
        ...

    @abstractmethod
    def request_upstream(self) -> None:
        """Request items from upstream components."""
        ...

    def phase1(self) -> None:
        """Reverse pass (sinks→sources): grant pulls + register demand on upstream."""
        self.fulfill_requests()
        self.request_upstream()

    def phase2(self) -> None:
        """Forward pass (sources→sinks): forward items received in Phase 1.
        Default no-op; override in components that want zero-tick passthrough."""

    def can_pull(self) -> bool:
        """Check whether this component currently has an item to provide.

        Returns:
            True if fulfill_requests() would be able to supply an item.
        """
        return False

    @abstractmethod
    def _accept_item(self, item: Item) -> bool:
        """Accept an incoming item from upstream.

        Args:
            item: The item being pushed into this component.

        Returns:
            True if the item was accepted, False otherwise.
        """
        ...