"""Monotonic integer ID generator for simulation components."""


class IDGen(object):
    """Generates monotonically increasing integer IDs.

    Useful for assigning unique identifiers to simulation components.
    """

    def __init__(self, start: int = 0) -> None:
        """Initialise the ID generator.

        Args:
            start: The value for the next ID to return. Defaults to 0.
        """
        self._next = start

    def next(self) -> int:
        """Return the next available ID and advance the counter.

        Returns:
            The next integer in the sequence (incremented by 1).
        """
        self._next += 1
        return self._next

    def reset(self, start: int = 0) -> None:
        """Reset the ID counter to a given starting value.

        Args:
            start: The value for the next ID to return (default 0).
        """
        self._next = start
