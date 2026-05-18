"""Grid-based component placement with overlap detection.

The Layout maps every occupied world cell to its component type+rotation.
Raise ``ValueError`` on construction if any two components overlap.
"""

from typing import Dict, Tuple, Set, Iterable, Optional, Any
from .utils import Vec
from ._enums import ComponentType, Rotation
from .mappings import get_metadata


class Layout(object):
    """Grid-based component placement with overlap detection.

    Maps every occupied world cell to its component type+rotation.
    Raises ``ValueError`` on construction if any two components overlap.
    """

    def __init__(self, layout: Dict[Vec, Tuple[ComponentType, Rotation]],
                 comp_configs: Optional[Dict[Vec, dict]] = None) -> None:
        """Build occupancy grid from a component layout dict.

        Iterates every component's coverage cells and checks for
        overlap before inserting into the grid.

        Args:
            layout: Maps each component's origin to its
                ``(ComponentType, Rotation)``.
            comp_configs: Optional per-origin config dicts forwarded to
                ``get_metadata``.

        Raises:
            ValueError: If two components occupy the same cell.
        """
        self.layout = layout
        self._meta_cfgs: Dict[Vec, dict] = comp_configs or {}
        self._grid: Dict[Vec, Tuple[ComponentType, Rotation]] = {}
        self._occupancy: Set[Vec] = set()

        for pos, (comp, rotation) in layout.items():
            cfg = self._meta_cfgs.get(pos, {})
            cov, _ = get_metadata(comp, **cfg)
            for offset in cov.cells(rotation):
                cell = pos + offset
                if cell in self._grid:
                    existing = self._grid[cell]
                    raise ValueError(f"Overlap at {cell}: {existing} and {(comp, rotation)}")
                self._grid[cell] = comp, rotation
                self._occupancy.add(cell)

    def is_occupied(self, coord: Vec) -> bool:
        """Check whether a world cell is occupied.

        Args:
            coord: World cell coordinate.

        Returns:
            True if the cell is occupied.
        """
        return coord in self._occupancy

    def get_component_at(self, coord: Vec) -> Optional[Tuple[ComponentType, Rotation]]:
        """Look up the component occupying a cell.

        Args:
            coord: World cell coordinate.

        Returns:
            The ``(ComponentType, Rotation)`` at *coord*, or None.
        """
        return self._grid.get(coord)

    def get(self, coord: Vec, default: Any = None) -> Tuple[ComponentType, Rotation] | Any:
        """Dict-style get with default.

        Args:
            coord: World cell coordinate.
            default: Value returned if the cell is unoccupied.

        Returns:
            The ``(ComponentType, Rotation)`` at *coord*, or *default*.
        """
        result = self.get_component_at(coord)
        if result is None:
            return default
        return result

    def __getitem__(self, coord: Vec) -> Tuple[ComponentType, Rotation]:
        """Look up a cell (raises KeyError if unoccupied).

        Args:
            coord: World cell coordinate.

        Returns:
            The ``(ComponentType, Rotation)`` at *coord*.

        Raises:
            KeyError: If the cell is not occupied.
        """
        return self._grid[coord]

    def get_all_components(self) -> Iterable[Tuple[Vec, Tuple[ComponentType, Rotation]]]:
        """Yield all (origin, (type, rotation)) pairs in insertion order.

        Yields:
            ``(Vec, (ComponentType, Rotation))`` for every component.
        """
        return self.layout.items()
