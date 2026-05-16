from ...base import Base

class BeltBridge(Base):
    def fulfill_requests(self) -> None:
        ...

    def request_upstream(self) -> None:
        ...

    def _accept_item(self, item) -> bool:
        return False