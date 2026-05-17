"""Item-control port — interface point for inserting or extracting items.

Not yet implemented; all methods are stubs.
"""

from ...base import Base


class ItemControlPort(Base):
    """Placeholder item control port (manual / automation I/O).

    Currently all methods are stubs that do nothing or reject items.
    """

    def fulfill_requests(self) -> None:
        """Stub — no-op. Placeholder for future downstream pull distribution."""
        ...

    def request_upstream(self) -> None:
        """Stub — no-op. Placeholder for future upstream pull requests."""
        ...

    def _accept_item(self, item) -> bool:
        """Stub — always rejects items.

        Args:
            item: The item to accept.

        Returns:
            False (item is always rejected).
        """
        return False