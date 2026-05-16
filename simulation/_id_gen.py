class IDGen(object):
    def __init__(self, start: int = 0) -> None:
        self._next = start

    def next(self) -> int:
        self._next += 1
        return self._next

    def reset(self, start: int = 0) -> None:
        self._next = start
