from .._enums import Direction, ComponentType, LinkType
from .._types import RelativeOffset
from .base import Base

import json


with open("../../assests/unit_metadata.json") as metadata:
    MAPPING = json.load(metadata)


# def get_link_type(source_component: Base, target_component: Base) -> LinkType:
#     pass