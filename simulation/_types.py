"""Type aliases used throughout the simulation package.

Coverage and RelativeOffset provide lightweight type hints for
grid dimensions and positional offsets.
"""

from typing import Tuple

Coverage = Tuple[int, int] # length, height

RelativeOffset = Tuple[int, int] # dx, dy