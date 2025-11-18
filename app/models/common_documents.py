from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class CommonDocumentCursor:
    id: int
    updated_at: str


@dataclass
class CommonDocumentsFetchResult:
    records: List[Dict[str, Any]]
    cursor: Optional[CommonDocumentCursor]


class CommonDocumentCursorModel(BaseModel):
    id: int
    updated_at: str = Field(alias="updatedAt")

    @classmethod
    def from_dataclass(cls, cursor: CommonDocumentCursor) -> "CommonDocumentCursorModel":
        return cls(id=cursor.id, updatedAt=cursor.updated_at)


class CommonDocumentFetchResponse(BaseModel):
    records: List[Dict[str, Any]]
    cursor: Optional[CommonDocumentCursorModel] = None


class CommonProductsResponse(BaseModel):
    products: List[str]
