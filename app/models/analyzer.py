from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.models.metadata import MetadataFilter


@dataclass
class AnalyzerClarification:
    reason: Optional[str] = None
    follow_up_prompt: Optional[str] = None
    message: Optional[str] = None
    options: Optional[List[str]] = None


@dataclass
class AnalyzerResult:
    filters: List[MetadataFilter]
    summaries: List[str]
    success: bool
    confidence: str
    clarification_needed: bool
    clarification: Optional[AnalyzerClarification]
    known_context: dict
    error: Optional[str] = None
