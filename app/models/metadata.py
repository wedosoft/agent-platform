from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MetadataOperator = Literal["EQUALS", "GREATER_THAN", "LESS_THAN", "IN"]


@dataclass
class MetadataFilter:
    key: str
    value: str
    operator: MetadataOperator = "EQUALS"
