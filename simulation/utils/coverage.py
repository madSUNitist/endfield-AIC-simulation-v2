"""Coverage abstractions: rectangular or path-based cell sets."""

from abc import ABC, abstractmethod
from typing import List

from . import Vec
from .._enums import Rotation


class Coverage(ABC):
    """Abstract footprint: the set of cell offsets a component occupies.

    Subclasses implement ``cells(rotation)`` which returns offset
    vectors relative to the component origin.
    """

    @abstractmethod
    def cells(self, rotation: Rotation) -> List[Vec]:
        ...


class AreaCoverage(Coverage):
    """Rectangular coverage — W × H grid cells oriented by rotation."""

    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h

    def cells(self, rotation: Rotation) -> List[Vec]:
        return [Vec(i, j) @ rotation for i in range(self.w) for j in range(self.h)]


def _expand(waypoints: List[List[int]]) -> List[Vec]:
    """Expand a list of waypoints into every grid cell along the path."""
    result: List[Vec] = []
    ox, oy = waypoints[0]
    for i in range(1, len(waypoints)):
        ax, ay = waypoints[i - 1]
        bx, by = waypoints[i]
        dx = bx - ax
        dy = by - ay
        sx = max(-1, min(1, dx))
        sy = max(-1, min(1, dy))
        step = Vec(sx, sy)
        steps = max(abs(dx), abs(dy))
        for k in range(steps):
            cell = Vec(ax + k * sx - ox, ay + k * sy - oy)
            if not result or cell != result[-1]:
                result.append(cell)
        # ensure last cell of this segment is included
        end = Vec(bx - ox, by - oy)
        if not result or end != result[-1]:
            result.append(end)
    if not result:
        result.append(Vec(0, 0))
    return result


class PathCoverage(Coverage):
    """Path-based coverage — every cell along a polyline."""

    def __init__(self, waypoints: List[List[int]]) -> None:
        self._offsets = _expand(waypoints)

    def cells(self, rotation: Rotation) -> List[Vec]:
        return list(self._offsets)
