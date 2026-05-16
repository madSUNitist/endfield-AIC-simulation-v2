from typing import Dict, Tuple, Set, Iterable, Optional, Any
from .utils import Vec
from ._enums import ComponentType, Rotation
from .mappings import get_metadata

class Layout(object):
    """Stores the component layout: occupancy queries, component lookup, and overlap detection."""
    
    def __init__(self, layout: Dict[Vec, Tuple[ComponentType, Rotation]]) -> None:
        """
        Args:
            layout: dict of top-left corner Vec -> (ComponentType, Rotation)
        Raises:
            ValueError: when component coverage areas overlap
        """
        self.layout = layout
        self._grid: Dict[Vec, Tuple[ComponentType, Rotation]] = {}
        self._occupancy: Set[Vec] = set()
        
        for pos, (comp, direction) in layout.items():
            cov, _ = get_metadata(comp)
            for offset in cov.coverage:
                cell = pos + offset
                if cell in self._grid:
                    existing = self._grid[cell]
                    raise ValueError(f"Overlap at {cell}: {existing} and {(comp, direction)}")
                self._grid[cell] = comp, direction
                self._occupancy.add(cell)

    def is_occupied(self, coord: Vec) -> bool:
        """Whether any component occupies the given coordinate."""
        return coord in self._occupancy

    def get_component_at(self, coord: Vec) -> Optional[Tuple[ComponentType, Rotation]]:
        """(ComponentType, Rotation) at the given coordinate, or None."""
        return self._grid.get(coord)
    
    def get(self, coord: Vec, default: Any = None) -> Tuple[ComponentType, Rotation] | Any:
        """(ComponentType, Rotation) at the given coordinate, or default."""
        result = self.get_component_at(coord)
        if result is None:
            return default
        
        return result
    
    def __getitem__(self, coord: Vec) -> Tuple[ComponentType, Rotation]:
        """(ComponentType, Rotation) at the given coordinate, or raise KeyError."""
        return self._grid[coord]

    def get_all_components(self) -> Iterable[Tuple[Vec, Tuple[ComponentType, Rotation]]]:
        """Iterate over all components: (top-left Vec, (ComponentType, Rotation))."""
        return self.layout.items()