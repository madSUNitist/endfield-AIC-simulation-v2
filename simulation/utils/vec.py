"""2-D integer vector with rotation support.

Vec is the fundamental coordinate type. The y-axis is treated as
"forward".  Supports addition, subtraction, rotation, and iteration
as a 2-tuple.
"""

from .._enums import Rotation, Direction


class Vec(object):
    """An integer 2-D vector with rotation semantics."""

    def __init__(self, x: int, y: int) -> None:
        """Args:
            x: X-coordinate component.
            y: Y-coordinate component (forward direction).
        """
        self.x, self.y = x, y
    
    def __hash__(self) -> int:
        return hash((self.x, self.y))
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vec) and self.x == other.x and self.y == other.y
    
    def __add__(self, other):
        """Vector addition.

        Args:
            other: Another Vec to add.

        Returns:
            A new Vec with component-wise sum.
        """
        assert isinstance(other, Vec), other
        return Vec(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        """Vector subtraction.

        Args:
            other: Another Vec to subtract.

        Returns:
            A new Vec with component-wise difference.
        """
        assert isinstance(other, Vec), other
        return Vec(self.x - other.x, self.y - other.y)
    
    def rotate(self, rotation: Rotation) -> "Vec":
        """Rotate this vector by the given rotation.

        Args:
            rotation: A Rotation enum value (ROT_0 through ROT_3).

        Returns:
            A new Vec representing the rotated vector.

        Raises:
            KeyError: If the rotation is not a valid Rotation value.
        """
        match rotation:
            case Rotation.ROT_0:
                return Vec(self.x, self.y)
            case Rotation.ROT_1:
                return Vec(-self.y, self.x)
            case Rotation.ROT_2:
                return Vec(-self.x, -self.y)
            case Rotation.ROT_3:
                return Vec(self.y, -self.x)
            case _:
                raise KeyError(rotation)
    
    def __matmul__(self, other):
        """Rotate this vector via the matrix-multiplication operator.

        Args:
            other: A Rotation to apply.

        Returns:
            The rotated Vec (equivalent to self.rotate(other)).
        """
        return self.rotate(other)
    
    def towards(self, direction: Direction) -> "Vec":
        """Return the adjacent cell in the given direction.

        Args:
            direction: A Direction enum.

        Returns:
            A new Vec offset by one step in the given direction.
        """
        return self + Vec(*direction.value)
    
    def __iter__(self):
        """Iterate over the components as a 2-tuple ``(x, y)``."""
        return iter((self.x, self.y))