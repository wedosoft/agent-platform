"""Supabase Knowledge Base 클라이언트.

kb_documents, kb_categories, kb_folders 테이블 접근을 위한 클라이언트.
Homepage 프로젝트의 hybrid_search RPC를 활용한 시맨틱 검색 지원.
"""

import logging
from functools import lru_cache
from typing import List, Optional

from supabase import create_client, Client

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase_kb_client() -> Client:
    """Supabase KB 클라이언트 싱글톤 반환."""
    settings = get_settings()

    if not settings.supabase_common_url or not settings.supabase_common_service_role_key:
        raise ValueError("Supabase KB credentials not configured")

    return create_client(
        settings.supabase_common_url,
        settings.supabase_common_service_role_key
    )


class KBClient:
    """Knowledge Base 데이터 접근 클래스."""

    def __init__(self):
        self.client = get_supabase_kb_client()

    # ============================================
    # 카테고리 조회
    # ============================================

    def get_categories(self, product_id: str) -> List[dict]:
        """제품별 카테고리 목록 조회."""
        result = self.client.table('kb_categories') \
            .select('id, name_en, name_ko, slug, description_en, description_ko, display_order') \
            .eq('product', product_id) \
            .eq('published', True) \
            .order('display_order') \
            .execute()

        return result.data or []

    def get_category_by_id(self, category_id: str) -> Optional[dict]:
        """카테고리 ID로 단일 조회."""
        result = self.client.table('kb_categories') \
            .select('id, name_en, name_ko, slug, description_en, description_ko, product') \
            .eq('id', category_id) \
            .single() \
            .execute()

        return result.data

    def get_category_by_slug(self, product_id: str, slug: str) -> Optional[dict]:
        """제품 + 슬러그로 카테고리 조회."""
        result = self.client.table('kb_categories') \
            .select('id, name_en, name_ko, slug, description_en, description_ko') \
            .eq('product', product_id) \
            .eq('slug', slug) \
            .eq('published', True) \
            .single() \
            .execute()

        return result.data

    # ============================================
    # 폴더 조회
    # ============================================

    def get_folders_by_category(self, product_id: str, category_id: str) -> List[dict]:
        """카테고리 내 폴더 목록 조회."""
        result = self.client.table('kb_folders') \
            .select('id, name_en, name_ko, slug, description_en, description_ko, display_order') \
            .eq('category_id', category_id) \
            .eq('product', product_id) \
            .eq('published', True) \
            .order('display_order') \
            .execute()

        return result.data or []

    # ============================================
    # 문서 조회
    # ============================================

    def get_documents_by_category(
        self,
        product_id: str,
        category_id: str,
        limit: int = 50
    ) -> List[dict]:
        """카테고리 내 모든 문서 조회 (폴더 경유)."""
        # 먼저 해당 카테고리의 폴더들을 조회
        folders = self.get_folders_by_category(product_id, category_id)
        folder_ids = [f['id'] for f in folders]

        if not folder_ids:
            return []

        result = self.client.table('kb_documents') \
            .select('id, csv_id, title_en, title_ko, content_text_ko, content_text_en, short_slug, slug, folder_id, display_order') \
            .eq('product', product_id) \
            .eq('published', True) \
            .in_('folder_id', folder_ids) \
            .order('display_order') \
            .limit(limit) \
            .execute()

        return result.data or []

    def get_documents_by_folder(
        self,
        product_id: str,
        folder_id: str,
        limit: int = 50
    ) -> List[dict]:
        """폴더 내 문서 조회."""
        result = self.client.table('kb_documents') \
            .select('id, csv_id, title_en, title_ko, content_text_ko, content_text_en, short_slug, slug, display_order') \
            .eq('product', product_id) \
            .eq('folder_id', folder_id) \
            .eq('published', True) \
            .order('display_order') \
            .limit(limit) \
            .execute()

        return result.data or []

    def get_document_by_id(self, doc_id: str) -> Optional[dict]:
        """문서 ID로 단일 조회."""
        result = self.client.table('kb_documents') \
            .select('id, csv_id, product, title_en, title_ko, content_html_ko, content_html_en, content_text_ko, content_text_en, short_slug, slug, tags') \
            .eq('id', doc_id) \
            .single() \
            .execute()

        return result.data

    # ============================================
    # 하이브리드 검색 (벡터 + 텍스트)
    # ============================================

    def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        product_filter: Optional[str] = None,
        match_count: int = 5,
        match_threshold: float = 0.5,
        dense_weight: float = 0.7,
        text_weight: float = 0.3
    ) -> List[dict]:
        """하이브리드 검색 (벡터 유사도 + 키워드 매칭).

        Args:
            query_embedding: 질문의 벡터 임베딩 (text-embedding-3-small)
            query_text: 질문 텍스트 (키워드 검색용)
            product_filter: 제품 ID 필터 (선택)
            match_count: 반환할 문서 수
            match_threshold: 유사도 임계값
            dense_weight: 벡터 유사도 가중치
            text_weight: 키워드 매칭 가중치

        Returns:
            검색 결과 문서 목록
        """
        result = self.client.rpc('hybrid_search', {
            'query_embedding': query_embedding,
            'query_text': query_text,
            'match_threshold': match_threshold,
            'match_count': match_count,
            'product_filter': product_filter,
            'dense_weight': dense_weight,
            'text_weight': text_weight
        }).execute()

        return result.data or []

    def search_documents(
        self,
        query_embedding: List[float],
        product_filter: Optional[str] = None,
        match_count: int = 5,
        match_threshold: float = 0.6
    ) -> List[dict]:
        """벡터 기반 시맨틱 검색.

        Args:
            query_embedding: 질문의 벡터 임베딩
            product_filter: 제품 ID 필터 (선택)
            match_count: 반환할 문서 수
            match_threshold: 유사도 임계값

        Returns:
            검색 결과 문서 목록
        """
        result = self.client.rpc('search_documents', {
            'query_embedding': query_embedding,
            'match_threshold': match_threshold,
            'match_count': match_count,
            'filter_product': product_filter
        }).execute()

        return result.data or []

    # ============================================
    # 텍스트 검색 (FTS)
    # ============================================

    def text_search(
        self,
        query: str,
        product_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """전문 검색 (PostgreSQL tsvector)."""
        # NOTE: postgrest-py(supabase 2.x)에서 `.text_search()`는 `SyncQueryRequestBuilder`를 반환해
        # `.limit()` 체이닝이 불가하므로, limit/range는 text_search 이전에 적용해야 한다.
        builder = self.client.table('kb_documents') \
            .select('id, csv_id, title_ko, title_en, content_text_ko, short_slug, product') \
            .eq('published', True)

        if product_filter:
            builder = builder.eq('product', product_filter)

        builder = builder.limit(limit).text_search('search_vector_ko', query.strip(), {
            'type': 'plain',
            'config': 'simple'
        })

        result = builder.execute()
        return result.data or []

    # ============================================
    # 통계
    # ============================================

    def get_product_stats(self, product_id: str) -> dict:
        """제품별 문서 통계."""
        # 카테고리 수
        categories = self.client.table('kb_categories') \
            .select('id', count='exact') \
            .eq('product', product_id) \
            .eq('published', True) \
            .execute()

        # 문서 수
        documents = self.client.table('kb_documents') \
            .select('id', count='exact') \
            .eq('product', product_id) \
            .eq('published', True) \
            .execute()

        return {
            'product_id': product_id,
            'category_count': categories.count or 0,
            'document_count': documents.count or 0
        }


# 싱글톤 인스턴스
_kb_client: Optional[KBClient] = None


def get_kb_client() -> KBClient:
    """KBClient 싱글톤 반환."""
    global _kb_client
    if _kb_client is None:
        _kb_client = KBClient()
    return _kb_client
