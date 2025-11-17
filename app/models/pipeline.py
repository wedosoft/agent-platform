from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class PipelineStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    ready: bool
    rag_store_name: Optional[str] = Field(default=None, alias="ragStoreName")
    rag_store_names: Optional[Dict[str, str]] = Field(default=None, alias="ragStoreNames")
    last_sync: Optional[Dict[str, Any]] = Field(default=None, alias="lastSync")
    progress: Optional[Dict[str, Any]] = None
    store_stats: Optional[Dict[str, Any]] = Field(default=None, alias="storeStats")
    available_sources: Optional[List[str]] = Field(default=None, alias="availableSources")


class CommonProductsResponse(BaseModel):
    products: List[str]


class SyncRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    include_tickets: Optional[bool] = Field(default=True, alias="includeTickets")
    include_articles: Optional[bool] = Field(default=True, alias="includeArticles")
    include_common_documents: Optional[bool] = Field(default=False, alias="includeCommonDocuments")
    incremental: Optional[bool] = False
    common_languages: Optional[List[str]] = Field(default=None, alias="commonLanguages")
    common_product: Optional[str] = Field(default=None, alias="commonProduct")
    common_document_limit: Optional[int] = Field(default=None, alias="commonDocumentLimit")
    ticket_since: Optional[str] = Field(default=None, alias="ticketSince")


class SyncResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    synced_at: str = Field(alias="syncedAt")
    ticket_count: int = Field(alias="ticketCount")
    article_count: int = Field(alias="articleCount")
    common_document_count: int = Field(alias="commonDocumentCount")
    errors: List[str]
    rag_store_name: Optional[str] = Field(default=None, alias="ragStoreName")
    rag_store_names: Optional[Dict[str, str]] = Field(default=None, alias="ragStoreNames")
