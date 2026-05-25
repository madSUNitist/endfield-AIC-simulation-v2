"""Grid-based component placement with overlap detection.

The Layout maps every occupied world cell to its component type+rotation.
Raise ``ValueError`` on construction if any two components overlap.
"""

from typing import Dict, Tuple, Set, List, Iterator, Optional, Any

from .utils import Vec
from ._enums import ComponentType, Rotation
from .mappings import get_metadata
from .placement import Placement


class Layout(object):
    """Grid-based component placement with overlap detection.

    Maps every occupied world cell to its component type+rotation.
    Raises ``ValueError`` on construction if any two components overlap.
    """

    def __init__(self, placements: List[Placement]) -> None:
        """Build occupancy grid from an ordered list of placements.

        Iterates every component's coverage cells and checks for
        overlap before inserting into the grid.

        Args:
            placements: Ordered list of component placements.
                The order is significant — it determines component IDs.

        Raises:
            ValueError: If two components occupy the same cell.
        """
        self._placements: List[Placement] = placements
        self._placement_map: Dict[Vec, Placement] = {pl.pos: pl for pl in placements}
        self._grid: Dict[Vec, Tuple[ComponentType, Rotation]] = {}
        self._occupancy: Set[Vec] = set()

        for pl in placements:
            cov, _ = get_metadata(pl.component_type, **pl.config)
            for offset in cov.cells(pl.rotation):
                cell = pl.pos + offset
                if cell in self._grid:
                    existing = self._grid[cell]
                    raise ValueError(
                        f"Overlap at {cell}: {existing} and {(pl.component_type, pl.rotation)}"
                    )
                self._grid[cell] = (pl.component_type, pl.rotation)
                self._occupancy.add(cell)

    def get_config(self, coord: Vec) -> dict:
        """Look up the config dict for a component by its origin.

        Args:
            coord: Grid origin of the component.

        Returns:
            The config dict, or an empty dict if not found.
        """
        pl = self._placement_map.get(coord)
        return pl.config if pl is not None else {}

    def is_occupied(self, coord: Vec) -> bool:
        """Check whether a world cell is occupied.

        Args:
            coord: World cell coordinate.

        Returns:
            True if the cell is occupied.
        """
        return coord in self._occupancy

    def can_place(self, placement: Placement) -> tuple[bool, str]:
        """Check whether *placement* can be added without overlap.

        Read-only — does not modify the layout.  Also detects
        self-intersection within the placement itself (e.g. a
        conveyor crossing its own path).

        Args:
            placement: The placement to check.

        Returns:
            ``(True, "")`` if the placement is valid,
            ``(False, reason)`` if it would cause an overlap.
        """
        cov, _ = get_metadata(placement.component_type, **placement.config)
        seen: set[Vec] = set()
        for offset in cov.cells(placement.rotation):
            cell = placement.pos + offset
            if cell in self._occupancy:
                return False, f"Overlap at ({cell.x},{cell.y})"
            if cell in seen:
                return False, f"Path self-intersects at ({cell.x},{cell.y})"
            seen.add(cell)
        return True, ""

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

    def get_all_components(self) -> Iterator[Placement]:
        """Yield all placements in insertion order.

        Yields:
            ``Placement`` for every component.
        """
        return iter(self._placements)
