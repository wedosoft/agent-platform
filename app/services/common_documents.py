from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from postgrest import APIResponse
from postgrest.types import CountMethod
from supabase import Client, create_client

from app.core.config import get_settings
from app.models.common_documents import (
    CommonDocumentCursor,
    CommonDocumentsFetchResult,
)

LOGGER = logging.getLogger(__name__)

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

SUPPORTED_LANGUAGES = ("ko", "en")


class CommonDocumentsError(RuntimeError):
    pass


@dataclass
class CommonDocumentsConfig:
    url: str
    service_role_key: str
    table_name: str = "documents"
    default_product: Optional[str] = None
    batch_size: int = 100
    languages: List[str] = field(default_factory=lambda: list(SUPPORTED_LANGUAGES))


class CommonDocumentsService:
    def __init__(self, config: CommonDocumentsConfig, *, client: Optional[Client] = None) -> None:
        if not config.url or not config.service_role_key:
            raise CommonDocumentsError("Supabase common configuration is incomplete")
        self.config = config
        self.client = client or create_client(config.url, config.service_role_key)

    def fetch_documents(
        self,
        *,
        limit: Optional[int] = None,
        product: Optional[str] = None,
        cursor: Optional[CommonDocumentCursor] = None,
        updated_since: Optional[str] = None,
    ) -> CommonDocumentsFetchResult:
        page_limit = limit or self.config.batch_size
        query = (
            self.client.table(self.config.table_name)
            .select(",".join(COMMON_DOCUMENT_COLUMNS))
            .order("updated_at", desc=False)
            .order("id", desc=False)
            .limit(page_limit)
        )

        effective_product = product or self.config.default_product
        if effective_product:
            query = query.eq("product", effective_product)

        if cursor:
            cursor_expression = (
                f"updated_at.gt.{cursor.updated_at},"
                f"and(updated_at.eq.{cursor.updated_at},id.gt.{cursor.id})"
            )
            query = query.or_(cursor_expression)
        elif updated_since:
            query = query.gte("updated_at", updated_since)

        response = query.execute()
        records = self._extract_records(response, "fetch documents")
        next_cursor = self._build_cursor(records)
        return CommonDocumentsFetchResult(records=records, cursor=next_cursor)

    def count_documents(self, product: Optional[str] = None) -> int:
        query = self.client.table(self.config.table_name).select(
            "id",
            count=CountMethod.exact,
            head=True,
        )
        effective_product = product or self.config.default_product
        if effective_product:
            query = query.eq("product", effective_product)

        response = query.execute()
        self._ensure_no_error(response, "count documents")
        return response.count or 0

    def list_products(self) -> List[str]:
        page_size = 1000
        seen = set()
        products: List[str] = []
        offset = 0

        while True:
            query = (
                self.client.table(self.config.table_name)
                .select("product")
                .order("product", desc=False)
                .range(offset, offset + page_size - 1)
            )
            response = query.execute()
            rows = self._extract_records(response, "list products")
            if not rows:
                break

            for row in rows:
                value = (row.get("product") or "").strip()
                if not value:
                    continue
                key = value.lower()
                if key in seen:
                    continue
                seen.add(key)
                products.append(value)

            if len(rows) < page_size:
                break
            offset += page_size

        products.sort(key=str.lower)
        return products

    def _build_cursor(
        self, records: List[Dict[str, Any]]
    ) -> Optional[CommonDocumentCursor]:
        if not records:
            return None
        last = records[-1]
        if "id" not in last or "updated_at" not in last:
            return None
        return CommonDocumentCursor(id=last["id"], updated_at=last["updated_at"])

    def _ensure_no_error(self, response: APIResponse, context: str) -> None:
        if getattr(response, "error", None):
            message = response.error.message if hasattr(response.error, "message") else str(response.error)
            LOGGER.error("Supabase %s failed: %s", context, message)
            raise CommonDocumentsError(f"Supabase {context} failed: {message}")

    def _extract_records(self, response: APIResponse, context: str) -> List[Dict[str, Any]]:
        self._ensure_no_error(response, context)
        data = response.data or []
        return list(data)


def _build_common_documents_service() -> CommonDocumentsService:
    settings = get_settings()
    if not settings.supabase_common_url or not settings.supabase_common_service_role_key:
        raise CommonDocumentsError("Supabase common environment variables are not set")

    languages = [
        lang.strip()
        for lang in (settings.supabase_common_languages or "ko,en").split(",")
        if lang.strip()
    ]
    config = CommonDocumentsConfig(
        url=settings.supabase_common_url,
        service_role_key=settings.supabase_common_service_role_key,
        table_name=settings.supabase_common_table_name,
        default_product=settings.supabase_common_default_product,
        batch_size=settings.supabase_common_batch_size,
        languages=languages or list(SUPPORTED_LANGUAGES),
    )
    return CommonDocumentsService(config)


@lru_cache
def get_common_documents_service() -> CommonDocumentsService:
    return _build_common_documents_service()
