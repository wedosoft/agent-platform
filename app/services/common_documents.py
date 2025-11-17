from __future__ import annotations

import math
import re
from datetime import datetime
from functools import lru_cache
from typing import List, Optional, Protocol

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.core.config import get_settings
from app.models.common_documents import (
    CommonDocumentCursor,
    CommonDocumentRecord,
    CommonDocumentsConfig,
    CommonDocumentsFetchOptions,
    CommonDocumentsFetchResult,
    GeminiDocumentChunk,
)

COMMON_DOCUMENT_COLUMNS = [
    "id",
    "csv_id",
    "product",
    "category_id",
    "folder_id",
    "title_en",
    "content_html_en",
    "content_text_en",
    "title_ko",
    "content_html_ko",
    "content_text_ko",
    "meta_title_en",
    "meta_title_ko",
    "meta_description_en",
    "meta_description_ko",
    "meta_keywords",
    "slug",
    "short_slug",
    "full_path",
    "tags",
    "visibility",
    "published",
    "created_at",
    "updated_at",
    "search_count",
    "hits",
    "thumbs_up",
    "thumbs_down",
]

SUPPORTED_LANGUAGES = {"ko", "en"}


class CommonDocumentsRepository(Protocol):
    def fetch_documents(self, options: CommonDocumentsFetchOptions) -> CommonDocumentsFetchResult:
        ...

    def count_documents(self, product: Optional[str] = None) -> int:
        ...

    def list_products(self) -> List[str]:
        ...


class SupabaseCommonDocumentsRepository:
    def __init__(self, config: CommonDocumentsConfig, client: Optional[Client] = None) -> None:
        if not config.url or not config.service_role_key:
            raise ValueError("Supabase URL과 Service Role Key는 필수입니다")
        self.config = config
        self._client = client or create_client(config.url, config.service_role_key)

    @property
    def client(self) -> Client:
        return self._client

    def fetch_documents(self, options: CommonDocumentsFetchOptions) -> CommonDocumentsFetchResult:
        limit = options.limit or self.config.batch_size
        query = (
            self.client.table(self.config.table_name)
            .select(
                ",".join(COMMON_DOCUMENT_COLUMNS),
                count=None,
            )
            .order("updated_at", desc=False)
            .order("id", desc=False)
            .limit(limit)
        )

        product = options.product or self.config.default_product
        if product:
            query = query.eq("product", product)

        if options.cursor:
            cursor_expr = self._build_cursor_filter(options.cursor)
            query = query.or_(cursor_expr)
        elif options.updated_since:
            query = query.gte("updated_at", options.updated_since.isoformat())

        response = query.execute()
        if response.error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "Supabase fetch failed", "details": response.error.message},
            )

        records = response.data or []
        cursor = self._derive_cursor(records, options.cursor)
        return CommonDocumentsFetchResult(records=records, cursor=cursor)

    def count_documents(self, product: Optional[str] = None) -> int:
        query = self.client.table(self.config.table_name).select("id", count="exact", head=True)
        target_product = product or self.config.default_product
        if target_product:
            query = query.eq("product", target_product)
        response = query.execute()
        if response.error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "Supabase count failed", "details": response.error.message},
            )
        return response.count or 0

    def list_products(self) -> List[str]:
        seen = set()
        products: List[str] = []
        page_size = 1000
        start = 0

        while True:
            query = (
                self.client.table(self.config.table_name)
                .select("product")
                .order("product", desc=False)
                .range(start, start + page_size - 1)
                .not_("product", "is", None)
            )
            response = query.execute()
            if response.error:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "Supabase product list failed", "details": response.error.message},
                )

            rows = response.data or []
            for row in rows:
                value = (row.get("product") or "").strip()
                if not value:
                    continue
                lowered = value.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                products.append(value)

            if len(rows) < page_size:
                break
            start += page_size

        return products

    def _build_cursor_filter(self, cursor: CommonDocumentCursor) -> str:
        return ",".join(
            [
                f"updated_at.gt.{cursor.updated_at}",
                f"and(updated_at.eq.{cursor.updated_at},id.gt.{cursor.id})",
            ]
        )

    def _derive_cursor(
        self,
        records: List[CommonDocumentRecord],
        existing: Optional[CommonDocumentCursor],
    ) -> Optional[CommonDocumentCursor]:
        if not records:
            return existing
        last = records[-1]
        if not last.get("updated_at"):
            return existing
        return CommonDocumentCursor(updatedAt=last["updated_at"], id=last["id"])


class CommonDocumentsService:
    def __init__(self, repository: CommonDocumentsRepository, config: CommonDocumentsConfig) -> None:
        self.repository = repository
        self.config = config

    def fetch_documents(self, options: CommonDocumentsFetchOptions) -> CommonDocumentsFetchResult:
        if not options.limit:
            options.limit = self.config.batch_size
        return self.repository.fetch_documents(options)

    def count_documents(self, product: Optional[str] = None) -> int:
        return self.repository.count_documents(product)

    def list_products(self) -> List[str]:
        return self.repository.list_products()

    def to_chunks(
        self,
        records: List[CommonDocumentRecord],
        languages: Optional[List[str]] = None,
    ) -> List[GeminiDocumentChunk]:
        target_languages = self._derive_languages(languages)
        chunks: List[GeminiDocumentChunk] = []

        for record in records:
            for language in target_languages:
                title, content = self._resolve_localized_content(record, language)
                if not title or not content:
                    continue
                normalized = self._normalize_text(content)
                for index, chunk_text in enumerate(self._chunk_content(normalized)):
                    chunk_id = f"common-{record.get('id')}-{language}-{index + 1}"
                    summary = self._build_summary(normalized) if self.config.summary_enabled else None
                    chunks.append(
                        GeminiDocumentChunk(
                            id=chunk_id,
                            content=chunk_text,
                            metadata=self._build_metadata(record, language, title, index),
                            summary=summary,
                        )
                    )
        return chunks

    def _derive_languages(self, languages: Optional[List[str]]) -> List[str]:
        if languages:
            normalized = [lang.strip().lower() for lang in languages if lang]
        else:
            normalized = [lang.strip().lower() for lang in self.config.languages]
        filtered = [lang for lang in normalized if lang in SUPPORTED_LANGUAGES]
        return filtered or ["ko", "en"]

    def _resolve_localized_content(
        self,
        record: CommonDocumentRecord,
        language: str,
    ) -> tuple[Optional[str], Optional[str]]:
        title_key = f"title_{language}"
        text_key = f"content_text_{language}"
        html_key = f"content_html_{language}"
        title = record.get(title_key)
        content = record.get(text_key) or self._strip_html(record.get(html_key))
        return title, content

    def _normalize_text(self, value: Optional[str]) -> str:
        if not value:
            return ""
        no_carriage = value.replace("\r", "\n")
        collapsed = re.sub(r"\s+", " ", no_carriage)
        return collapsed.strip()

    def _strip_html(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        text = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", text).strip()

    def _chunk_content(self, content: str) -> List[str]:
        if not content:
            return []
        max_chars = max(200, self.config.max_document_chars)
        overlap = max(0, min(self.config.chunk_overlap, max_chars // 2))
        chunks: List[str] = []
        start = 0
        length = len(content)
        while start < length:
            end = min(length, start + max_chars)
            chunks.append(content[start:end])
            if end >= length:
                break
            start = max(0, end - overlap)
            if start >= length:
                break
        return chunks

    def _build_summary(self, content: str) -> Optional[str]:
        if not content:
            return None
        max_chars = max(100, self.config.summary_max_chars)
        if len(content) <= max_chars:
            return content
        return f"{content[:max_chars].rstrip()}…"

    def _build_metadata(
        self,
        record: CommonDocumentRecord,
        language: str,
        title: str,
        chunk_index: int,
    ) -> dict:
        metadata = {
            "documentId": record.get("id"),
            "language": language,
            "title": title,
            "product": record.get("product"),
            "slug": record.get("slug") or record.get("full_path"),
            "chunkIndex": chunk_index,
        }
        return {key: value for key, value in metadata.items() if value is not None}


@lru_cache
def get_common_documents_service() -> CommonDocumentsService:
    settings = get_settings()
    if not settings.supabase_common_url or not settings.supabase_common_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase 공통 문서 구성이 누락되었습니다",
        )
    config = CommonDocumentsConfig(
        url=settings.supabase_common_url,
        serviceRoleKey=settings.supabase_common_service_role_key,
        tableName=settings.supabase_common_table_name,
        defaultProduct=settings.supabase_common_default_product,
        batchSize=settings.supabase_common_batch_size,
        languages=settings.supabase_common_languages,
        maxDocumentChars=settings.supabase_common_max_document_chars,
        chunkOverlap=settings.supabase_common_chunk_overlap,
        summaryEnabled=settings.supabase_common_summary_enabled,
        summaryMaxChars=settings.supabase_common_summary_max_chars,
    )
    repository = SupabaseCommonDocumentsRepository(config)
    return CommonDocumentsService(repository, config)
