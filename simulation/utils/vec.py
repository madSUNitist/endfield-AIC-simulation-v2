from .._enums import Rotation, Direction


class Vec(object):
    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y
    
    def __hash__(self) -> int:
        return hash((self.x, self.y))
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vec) and self.x == other.x and self.y == other.y
    
    def __add__(self, other):
        assert isinstance(other, Vec), other
        return Vec(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        assert isinstance(other, Vec), other
        return Vec(self.x - other.x, self.y - other.y)
    
    def rotate(self, rotation: Rotation) -> "Vec":
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
        return self.rotate(other)
    
    def towards(self, direction: Direction) -> "Vec":
        return self + Vec(*direction.value)
    
    def __iter__(self):
        return iter((self.x, self.y))