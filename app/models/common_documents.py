from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from pydantic import BaseModel, Field


class CommonDocumentRecord(TypedDict, total=False):
    id: int
    csv_id: Optional[str]
    product: Optional[str]
    category_id: Optional[int]
    folder_id: Optional[int]
    title_en: Optional[str]
    content_html_en: Optional[str]
    content_text_en: Optional[str]
    title_ko: Optional[str]
    content_html_ko: Optional[str]
    content_text_ko: Optional[str]
    meta_title_en: Optional[str]
    meta_title_ko: Optional[str]
    meta_description_en: Optional[str]
    meta_description_ko: Optional[str]
    meta_keywords: Optional[str]
    slug: Optional[str]
    short_slug: Optional[str]
    full_path: Optional[str]
    tags: Optional[str]
    visibility: Optional[str]
    published: Optional[bool]
    created_at: Optional[str]
    updated_at: Optional[str]
    search_count: Optional[int]
    hits: Optional[int]
    thumbs_up: Optional[int]
    thumbs_down: Optional[int]


class CommonDocumentCursor(BaseModel):
    updated_at: str = Field(alias="updatedAt")
    id: int


class CommonDocumentsFetchOptions(BaseModel):
    limit: Optional[int] = None
    product: Optional[str] = None
    updated_since: Optional[datetime] = Field(default=None, alias="updatedSince")
    cursor: Optional[CommonDocumentCursor] = None


class CommonDocumentsFetchResult(BaseModel):
    records: List[CommonDocumentRecord]
    cursor: Optional[CommonDocumentCursor] = None


class GeminiDocumentChunk(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    summary: Optional[str] = None


class CommonDocumentsConfig(BaseModel):
    url: str
    service_role_key: str = Field(alias="serviceRoleKey")
    table_name: str = Field(default="documents", alias="tableName")
    default_product: Optional[str] = Field(default=None, alias="defaultProduct")
    batch_size: int = Field(default=10, alias="batchSize")
    languages: List[str] = Field(default_factory=lambda: ["ko", "en"])
    max_document_chars: int = Field(default=4000, alias="maxDocumentChars")
    chunk_overlap: int = Field(default=200, alias="chunkOverlap")
    summary_enabled: bool = Field(default=False, alias="summaryEnabled")
    summary_max_chars: int = Field(default=500, alias="summaryMaxChars")

    model_config = {
        "populate_by_name": True,
    }
