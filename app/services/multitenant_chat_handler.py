"""
Multitenant Chat Handler

Extends common chat handling with tenant-aware filtering and store routing.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.middleware.tenant_auth import TenantContext
from app.models.metadata import MetadataFilter
from app.models.session import ChatRequest, ChatResponse
from app.services.gemini_client import GeminiClientError
from app.services.gemini_file_search_client import GeminiFileSearchClient

LOGGER = logging.getLogger(__name__)

# Shared store names (configured via environment)
SHARED_TICKET_STORE = os.getenv("SHARED_TICKET_STORE", "fileSearchStores/tickets-shared")
SHARED_ARTICLE_STORE = os.getenv("SHARED_ARTICLE_STORE", "fileSearchStores/articles-shared")
SHARED_COMMON_STORE = os.getenv("SHARED_COMMON_STORE")  # From settings


SYSTEM_INSTRUCTION = (
    "You are a helpful customer support assistant. "
    "Answer ONLY the user's CURRENT question based on the provided search results (Context). "
    "Do NOT repeat or re-answer previous questions from the conversation history. "
    "If the answer is not in the context, politely state that you cannot find the information. "
    "Keep your response focused and concise."
)


class MultitenantChatHandler:
    """Chat handler with multitenant support."""

    def __init__(
        self,
        *,
        gemini_client: GeminiFileSearchClient,
        shared_ticket_store: Optional[str] = None,
        shared_article_store: Optional[str] = None,
        shared_common_store: Optional[str] = None,
    ) -> None:
        self.gemini_client = gemini_client
        self.shared_ticket_store = shared_ticket_store or SHARED_TICKET_STORE
        self.shared_article_store = shared_article_store or SHARED_ARTICLE_STORE
        self.shared_common_store = shared_common_store or SHARED_COMMON_STORE

    def _resolve_stores(
        self,
        request: ChatRequest,
        tenant: TenantContext,
    ) -> List[str]:
        """
        Resolve which stores to search based on request and tenant config.
        
        Priority:
        1. Explicit sources in request
        2. Tenant's custom stores (if configured)
        3. Shared stores with tenant filtering
        """
        # If specific sources requested, use them
        if request.sources:
            return [s.strip() for s in request.sources if s.strip()]
        
        # Default: use shared stores (common for product docs doesn't need tenant filter)
        stores = []
        
        # Add ticket store
        if self.shared_ticket_store:
            stores.append(self.shared_ticket_store)
        
        # Add article store
        if self.shared_article_store:
            stores.append(self.shared_article_store)
        
        return stores

    def _build_mandatory_filters(
        self,
        tenant: TenantContext,
        request: ChatRequest,
    ) -> List[MetadataFilter]:
        """
        Build mandatory filters for tenant isolation.
        
        These filters are ALWAYS applied to ensure data isolation.
        """
        filters = tenant.get_mandatory_filters()
        
        # Add product filter if specified
        if request.common_product:
            filters.append(
                MetadataFilter(
                    key="product",
                    value=request.common_product.strip(),
                    operator="EQUALS",
                )
            )
        
        return filters

    async def handle(
        self,
        request: ChatRequest,
        tenant: TenantContext,
        *,
        history: Optional[List[dict]] = None,
        additional_filters: Optional[List[MetadataFilter]] = None,
    ) -> ChatResponse:
        """
        Handle chat request with tenant context.
        
        Args:
            request: The chat request
            tenant: Authenticated tenant context
            history: Conversation history
            additional_filters: Extra filters (e.g., from query analyzer)
        """
        # Resolve stores
        store_names = self._resolve_stores(request, tenant)
        
        if not store_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No search stores available for this tenant",
            )
        
        # Build filters
        mandatory_filters = self._build_mandatory_filters(tenant, request)
        all_filters = mandatory_filters + (additional_filters or [])
        
        # Build filter summaries for response
        filter_summaries = [
            f"{f.key}={f.value}" for f in all_filters if f.key not in ("tenant_id", "platform")
        ]
        
        # Log search details
        LOGGER.info(
            "Multitenant search: tenant=%s, platform=%s, stores=%s, filters=%s",
            tenant.tenant_id,
            tenant.platform,
            store_names,
            [f.key for f in all_filters],
        )
        
        try:
            result = await self.gemini_client.search(
                query=request.query,
                store_names=store_names,
                metadata_filters=all_filters,
                conversation_history=history,
                system_instruction=SYSTEM_INSTRUCTION,
            )
        except GeminiClientError as exc:
            LOGGER.exception("Gemini search failed for tenant %s", tenant.tenant_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        
        payload = {
            "text": result["text"],
            "groundingChunks": result.get("grounding_chunks", []),
            "ragStoreName": store_names[0] if store_names else None,
            "sources": store_names,
            "filters": filter_summaries,
            "knownContext": {
                "tenant_id": tenant.tenant_id,
                "platform": tenant.platform,
            },
        }
        
        return ChatResponse.model_validate(payload)

    async def stream_handle(
        self,
        request: ChatRequest,
        tenant: TenantContext,
        *,
        history: Optional[List[str]] = None,
        additional_filters: Optional[List[MetadataFilter]] = None,
    ):
        """
        Stream chat response with tenant context.
        """
        # Resolve stores
        store_names = self._resolve_stores(request, tenant)
        
        if not store_names:
            yield {
                "event": "error",
                "data": {"message": "No search stores available for this tenant"},
            }
            return
        
        # Build filters
        mandatory_filters = self._build_mandatory_filters(tenant, request)
        all_filters = mandatory_filters + (additional_filters or [])
        
        filter_summaries = [
            f"{f.key}={f.value}" for f in all_filters if f.key not in ("tenant_id", "platform")
        ]
        
        LOGGER.info(
            "Multitenant stream search: tenant=%s, platform=%s, stores=%s",
            tenant.tenant_id,
            tenant.platform,
            store_names,
        )
        
        try:
            async for event in self.gemini_client.stream_search(
                query=request.query,
                store_names=store_names,
                metadata_filters=all_filters,
                conversation_history=history,
                system_instruction=SYSTEM_INSTRUCTION,
            ):
                if event["event"] == "result":
                    payload = event["data"]
                    payload.update({
                        "ragStoreName": store_names[0] if store_names else None,
                        "sources": store_names,
                        "filters": filter_summaries,
                        "knownContext": {
                            "tenant_id": tenant.tenant_id,
                            "platform": tenant.platform,
                        },
                    })
                    yield {"event": "result", "data": payload}
                else:
                    yield event
        except GeminiClientError as exc:
            LOGGER.exception("Gemini stream failed for tenant %s", tenant.tenant_id)
            yield {
                "event": "error",
                "data": {"message": str(exc) or "잠시 후 다시 시도해 주세요."},
            }


def get_multitenant_chat_handler() -> Optional[MultitenantChatHandler]:
    """Factory function to create MultitenantChatHandler."""
    settings = get_settings()
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return None
    
    client = GeminiFileSearchClient(
        api_key=api_key,
        primary_model=settings.gemini_primary_model,
        fallback_model=settings.gemini_fallback_model,
    )
    
    return MultitenantChatHandler(
        gemini_client=client,
        shared_common_store=settings.gemini_store_common,
    )
