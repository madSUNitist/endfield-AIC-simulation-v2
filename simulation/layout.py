"""Grid-based component placement with overlap detection."""

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
        """Check whether a world cell is occupied."""
        return coord in self._occupancy

    def get_component_at(self, coord: Vec) -> Optional[Tuple[ComponentType, Rotation]]:
        """Look up the component occupying a cell."""
        return self._grid.get(coord)

    def get(self, coord: Vec, default: Any = None) -> Tuple[ComponentType, Rotation] | Any:
        """Dict-style get with default."""
        result = self.get_component_at(coord)
        if result is None:
            return default
        return result

    def __getitem__(self, coord: Vec) -> Tuple[ComponentType, Rotation]:
        """Dict-style lookup (raises KeyError if unoccupied)."""
        return self._grid[coord]

    def get_all_components(self) -> Iterable[Tuple[Vec, Tuple[ComponentType, Rotation]]]:
        """Yield all (origin, (type, rotation)) pairs in insertion order."""
        return self.layout.items()
