from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EntityMatch:
    id: int
    type: str
    name: str
    email: Optional[str] = None
    confidence: float = 1.0
    source: str = "exact"
    details: dict = field(default_factory=dict)


@dataclass
class EntityResolutionResult:
    matches: List[EntityMatch]
    clarification_needed: bool
    reason: Optional[str] = None
