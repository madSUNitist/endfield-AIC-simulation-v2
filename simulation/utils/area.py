"""Utility class representing a rectangular area with coverage iteration."""

from typing import Iterable

from . import Vec


class Area(object):
    """W × H rectangle that yields offset vectors for each cell."""

    def __init__(self, w: int, h: int) -> None:
        """Initialise a rectangular area.

        Args:
            w: Width in cells.
            h: Height in cells.
        """
        self.w, self.h = w, h
        self.area = w * h

    @property
    def coverage(self) -> Iterable[Vec]:
        """Yield offset vectors for every cell in the rectangle."""
        for i in range(self.w):
            for j in range(self.h):
                yield Vec(i, j)
