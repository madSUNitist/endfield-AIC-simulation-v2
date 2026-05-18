"""Coverage abstractions — rectangular or path-based cell sets.

Each Coverage subclass computes the set of cell offsets a component
occupies on the grid, given a rotation.
"""

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
        """Return all offset vectors occupied by this footprint.

        Args:
            rotation: The rotation to apply.

        Returns:
            List of Vec offsets relative to the component origin.
        """
        ...


class AreaCoverage(Coverage):
    """Rectangular coverage — W × H grid cells oriented by rotation."""

    def __init__(self, w: int, h: int) -> None:
        """Initialise a rectangular coverage.

        Args:
            w: Width in cells.
            h: Height in cells.
        """
        self.w = w
        self.h = h

    def cells(self, rotation: Rotation) -> List[Vec]:
        """Generate all offset vectors for the rectangle.

        Args:
            rotation: The rotation to apply.

        Returns:
            List of :math:`W \\times H` offset Vecs.
        """
        return [Vec(i, j) @ rotation for i in range(self.w) for j in range(self.h)]


def _expand(waypoints: List[List[int]]) -> List[Vec]:
    """Expand a list of waypoints into every grid cell along the path.

    Args:
        waypoints: List of ``[x, y]`` coordinates defining a polyline.

    Returns:
        Flattened list of cell-offset Vecs covering the entire path.
    """
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
        """Initialise a path-based coverage.

        Args:
            waypoints: List of ``[x, y]`` coordinates defining the polyline.
        """
        self._offsets = _expand(waypoints)

    def cells(self, rotation: Rotation) -> List[Vec]:
        """Return the pre-computed offset vectors.

        Args:
            rotation: Ignored (path offsets are absolute).

        Returns:
            A copy of the stored offset list.
        """
        return list(self._offsets)
