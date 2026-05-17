"""Utility class representing a rectangular area with coverage iteration."""

from typing import Iterable

from . import Vec


class Area(object):
    """W × H rectangle that yields offset vectors for each cell."""

    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.area = w * h

    @property
    def coverage(self) -> Iterable[Vec]:
        for i in range(self.w):
            for j in range(self.h):
                yield Vec(i, j)
