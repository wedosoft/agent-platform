"""제품 저장소 - 제품, 카테고리, 폴더, 문서 통합 관리."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)

PRODUCTS_FALLBACK = [
    {
        "id": "freshservice",
        "name": "Freshservice",
        "name_ko": "프레시서비스",
        "description": "IT Service Management",
        "description_ko": "IT 서비스 관리",
        "icon": "cog",
        "color": "blue",
        "product_type": "standalone",
        "display_order": 1,
    },
    {
        "id": "freshdesk",
        "name": "Freshdesk",
        "name_ko": "프레시데스크",
        "description": "Customer Support",
        "description_ko": "고객 지원",
        "icon": "headset",
        "color": "green",
        "product_type": "standalone",
        "display_order": 2,
    },
    {
        "id": "freshdesk_omni",
        "name": "Freshdesk Omni",
        "name_ko": "프레시데스크 옴니",
        "description": "Unified Customer Experience",
        "description_ko": "통합 고객 경험",
        "icon": "layer-group",
        "color": "teal",
        "product_type": "bundle",
        "display_order": 3,
    },
    {
        "id": "freshsales",
        "name": "Freshsales",
        "name_ko": "프레시세일즈",
        "description": "CRM & Sales",
        "description_ko": "CRM 및 영업",
        "icon": "chart-line",
        "color": "purple",
        "product_type": "standalone",
        "display_order": 4,
    },
    {
        "id": "freshchat",
        "name": "Freshchat",
        "name_ko": "프레시챗",
        "description": "Messaging & Chat",
        "description_ko": "메시징 및 채팅",
        "icon": "comments",
        "color": "orange",
        "product_type": "standalone",
        "display_order": 5,
    },
]


class Product(BaseModel):
    """제품 모델."""
    id: str
    name: str
    name_ko: str
    description: str = ""
    description_ko: str = ""
    icon: str = "cube"
    color: str = "blue"
    product_type: str = "standalone"
    display_order: int = 99


class ProductCategory(BaseModel):
    """제품 카테고리 모델."""
    id: str
    product_id: str
    name: str
    name_ko: str
    description: Optional[str] = None
    description_ko: Optional[str] = None
    icon: Optional[str] = None
    display_order: int = 0
    document_count: int = 0


class ProductFolder(BaseModel):
    """제품 폴더 모델."""
    id: str
    category_id: str
    name: str
    name_ko: str
    description: Optional[str] = None
    display_order: int = 0
    document_count: int = 0


class ProductDocument(BaseModel):
    """제품 문서 모델."""
    id: str
    folder_id: Optional[str] = None
    category_id: str
    title: str
    title_ko: str
    content: Optional[str] = None
    content_ko: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    display_order: int = 0


class ProductRepositoryError(RuntimeError):
    """제품 저장소 에러."""
    pass


class ProductRepository:
    """제품 저장소 (제품, 카테고리, 폴더, 문서 통합 관리)."""

    def __init__(self, client: Client) -> None:
        self.client = client
        self._products_cache: Optional[List[Product]] = None

    def _get_public_client(self) -> Client:
        """public 스키마용 클라이언트 반환."""
        settings = get_settings()
        if not settings.supabase_common_url or not settings.supabase_common_service_role_key:
            raise ProductRepositoryError("Supabase 설정이 없습니다.")
        
        return create_client(
            settings.supabase_common_url,
            settings.supabase_common_service_role_key,
            options=ClientOptions(schema="public"),
        )

    def _is_table_missing_error(self, exc: Exception) -> bool:
        """테이블 미존재 에러 여부 확인."""
        text = str(exc)
        return "PGRST205" in text or ("schema cache" in text and "Could not find the table" in text)

    def _normalize_product_row(
        self,
        row: Dict[str, Any],
        product_type: str = "standalone",
    ) -> Optional[Product]:
        """DB 행을 Product 모델로 변환."""
        product_id = row.get("id")
        if not product_id:
            return None

        name = row.get("name_en") or row.get("name") or row.get("nameEn") or product_id
        name_ko = row.get("name_ko") or row.get("nameKo") or name
        description = row.get("description_en") or row.get("description") or ""
        description_ko = row.get("description_ko") or ""
        icon = row.get("icon") or ("layer-group" if product_type == "bundle" else "cube")
        color = row.get("color") or row.get("color_primary") or ("teal" if product_type == "bundle" else "blue")
        display_order = row.get("display_order", 99)

        return Product(
            id=product_id,
            name=name,
            name_ko=name_ko,
            description=description,
            description_ko=description_ko,
            icon=icon,
            color=color,
            product_type=product_type,
            display_order=display_order,
        )

    def _sort_products(self, products: List[Product]) -> List[Product]:
        """제품 목록 정렬."""
        return sorted(products, key=lambda x: (x.display_order, x.id))

    def _fetch_products_from_tables(self, client: Client) -> List[Product]:
        """product_modules + product_bundles 테이블에서 제품 조회."""
        products: List[Product] = []

        try:
            modules_resp = (
                client.table("product_modules")
                .select("*")
                .eq("is_active", True)
                .order("display_order")
                .execute()
            )
            for row in modules_resp.data or []:
                product = self._normalize_product_row(row, product_type="standalone")
                if product:
                    products.append(product)
        except Exception as e:
            if not self._is_table_missing_error(e):
                LOGGER.warning(f"Failed to fetch product_modules: {e}")

        try:
            bundles_resp = (
                client.table("product_bundles")
                .select("*")
                .eq("is_active", True)
                .order("display_order")
                .execute()
            )
            for row in bundles_resp.data or []:
                product = self._normalize_product_row(row, product_type="bundle")
                if product:
                    products.append(product)
        except Exception as e:
            if not self._is_table_missing_error(e):
                LOGGER.warning(f"Failed to fetch product_bundles: {e}")

        return self._sort_products(products)

    def _fetch_products_from_curriculum_modules(self, client: Client) -> List[Product]:
        """curriculum_modules에서 제품 목록 유도."""
        try:
            resp = (
                client.table("curriculum_modules")
                .select("target_product_id, target_product_type")
                .eq("is_active", True)
                .execute()
            )
        except Exception as e:
            LOGGER.warning(f"Failed to fetch curriculum_modules: {e}")
            return []

        fallback_by_id = {p["id"]: p for p in PRODUCTS_FALLBACK}
        seen: Dict[str, str] = {}
        
        for row in resp.data or []:
            product_id = row.get("target_product_id")
            product_type_raw = row.get("target_product_type") or "module"
            if not product_id:
                continue
            seen[product_id] = "bundle" if product_type_raw == "bundle" else "standalone"

        if not seen:
            return []

        products: List[Product] = []
        for product_id, product_type in seen.items():
            base = fallback_by_id.get(product_id, {})
            products.append(Product(
                id=product_id,
                name=base.get("name") or product_id,
                name_ko=base.get("name_ko") or base.get("name") or product_id,
                description=base.get("description") or "",
                description_ko=base.get("description_ko") or "",
                icon=base.get("icon") or ("layer-group" if product_type == "bundle" else "cube"),
                color=base.get("color") or ("teal" if product_type == "bundle" else "blue"),
                product_type=product_type,
                display_order=base.get("display_order", 99),
            ))

        return self._sort_products(products)

    # ============================================
    # 제품 조회
    # ============================================

    def get_products(self, use_cache: bool = True) -> List[Product]:
        """제품 목록 조회 (캐시 지원)."""
        if use_cache and self._products_cache is not None:
            return self._products_cache

        products = self._fetch_products_from_tables(self.client)
        if products:
            self._products_cache = products
            return products

        try:
            public_client = self._get_public_client()
            products = self._fetch_products_from_tables(public_client)
            if products:
                self._products_cache = products
                return products
        except Exception as e:
            LOGGER.warning(f"Failed to fetch from public schema: {e}")

        products = self._fetch_products_from_curriculum_modules(self.client)
        if products:
            self._products_cache = products
            return products

        fallback = [Product(**p) for p in PRODUCTS_FALLBACK]
        self._products_cache = fallback
        return fallback

    def get_product(self, product_id: str) -> Optional[Product]:
        """제품 단건 조회."""
        products = self.get_products()
        for product in products:
            if product.id == product_id:
                return product
        return None

    def get_products_by_ids(self, product_ids: List[str]) -> List[Product]:
        """여러 제품 조회."""
        products = self.get_products()
        return [p for p in products if p.id in product_ids]

    def clear_cache(self) -> None:
        """캐시 초기화."""
        self._products_cache = None

    # ============================================
    # 카테고리 조회
    # ============================================

    def get_categories(self, product_id: str) -> List[ProductCategory]:
        """제품별 카테고리 목록 조회."""
        try:
            resp = (
                self.client.table("product_categories")
                .select("*")
                .eq("product_id", product_id)
                .order("display_order")
                .execute()
            )
            
            categories = []
            for row in resp.data or []:
                categories.append(ProductCategory(
                    id=row["id"],
                    product_id=row["product_id"],
                    name=row.get("name_en") or row.get("name") or row["id"],
                    name_ko=row.get("name_ko") or row.get("name") or row["id"],
                    description=row.get("description_en") or row.get("description"),
                    description_ko=row.get("description_ko"),
                    icon=row.get("icon"),
                    display_order=row.get("display_order", 0),
                    document_count=row.get("document_count", 0),
                ))
            return categories
        except Exception as e:
            LOGGER.error(f"Failed to get categories for product {product_id}: {e}")
            return []

    def get_category(self, category_id: str) -> Optional[ProductCategory]:
        """카테고리 단건 조회."""
        try:
            resp = (
                self.client.table("product_categories")
                .select("*")
                .eq("id", category_id)
                .limit(1)
                .execute()
            )
            
            if resp.data:
                row = resp.data[0]
                return ProductCategory(
                    id=row["id"],
                    product_id=row["product_id"],
                    name=row.get("name_en") or row.get("name") or row["id"],
                    name_ko=row.get("name_ko") or row.get("name") or row["id"],
                    description=row.get("description_en") or row.get("description"),
                    description_ko=row.get("description_ko"),
                    icon=row.get("icon"),
                    display_order=row.get("display_order", 0),
                    document_count=row.get("document_count", 0),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get category {category_id}: {e}")
            return None

    # ============================================
    # 폴더 조회
    # ============================================

    def get_folders(self, category_id: str) -> List[ProductFolder]:
        """카테고리별 폴더 목록 조회."""
        try:
            resp = (
                self.client.table("product_folders")
                .select("*")
                .eq("category_id", category_id)
                .order("display_order")
                .execute()
            )
            
            folders = []
            for row in resp.data or []:
                folders.append(ProductFolder(
                    id=row["id"],
                    category_id=row["category_id"],
                    name=row.get("name_en") or row.get("name") or row["id"],
                    name_ko=row.get("name_ko") or row.get("name") or row["id"],
                    description=row.get("description"),
                    display_order=row.get("display_order", 0),
                    document_count=row.get("document_count", 0),
                ))
            return folders
        except Exception as e:
            LOGGER.error(f"Failed to get folders for category {category_id}: {e}")
            return []

    # ============================================
    # 문서 조회
    # ============================================

    def get_documents(
        self,
        category_id: str,
        folder_id: Optional[str] = None,
    ) -> List[ProductDocument]:
        """카테고리/폴더별 문서 목록 조회."""
        try:
            query = (
                self.client.table("product_documents")
                .select("*")
                .eq("category_id", category_id)
            )
            
            if folder_id:
                query = query.eq("folder_id", folder_id)
            
            resp = query.order("display_order").execute()
            
            documents = []
            for row in resp.data or []:
                documents.append(ProductDocument(
                    id=row["id"],
                    folder_id=row.get("folder_id"),
                    category_id=row["category_id"],
                    title=row.get("title_en") or row.get("title") or row["id"],
                    title_ko=row.get("title_ko") or row.get("title") or row["id"],
                    content=row.get("content_en") or row.get("content"),
                    content_ko=row.get("content_ko"),
                    file_url=row.get("file_url"),
                    file_type=row.get("file_type"),
                    display_order=row.get("display_order", 0),
                ))
            return documents
        except Exception as e:
            LOGGER.error(f"Failed to get documents for category {category_id}: {e}")
            return []

    def get_document(self, document_id: str) -> Optional[ProductDocument]:
        """문서 단건 조회."""
        try:
            resp = (
                self.client.table("product_documents")
                .select("*")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
            
            if resp.data:
                row = resp.data[0]
                return ProductDocument(
                    id=row["id"],
                    folder_id=row.get("folder_id"),
                    category_id=row["category_id"],
                    title=row.get("title_en") or row.get("title") or row["id"],
                    title_ko=row.get("title_ko") or row.get("title") or row["id"],
                    content=row.get("content_en") or row.get("content"),
                    content_ko=row.get("content_ko"),
                    file_url=row.get("file_url"),
                    file_type=row.get("file_type"),
                    display_order=row.get("display_order", 0),
                )
            return None
        except Exception as e:
            LOGGER.error(f"Failed to get document {document_id}: {e}")
            return None

    # ============================================
    # RAG 필터 생성
    # ============================================

    def get_rag_filters_for_product(self, product_id: str) -> Dict[str, Any]:
        """제품별 RAG 검색 필터 생성."""
        product = self.get_product(product_id)
        if not product:
            return {}

        return {
            "product_id": product_id,
            "product_name": product.name,
            "product_name_ko": product.name_ko,
        }

    def get_rag_filters_for_category(self, category_id: str) -> Dict[str, Any]:
        """카테고리별 RAG 검색 필터 생성."""
        category = self.get_category(category_id)
        if not category:
            return {}

        product = self.get_product(category.product_id)
        
        return {
            "product_id": category.product_id,
            "product_name": product.name if product else category.product_id,
            "category_id": category_id,
            "category_name": category.name,
            "category_name_ko": category.name_ko,
        }


@lru_cache
def get_product_repository_instance(supabase_url: str, supabase_key: str, schema: str = "onboarding") -> ProductRepository:
    """ProductRepository 싱글톤 인스턴스 반환."""
    client = create_client(
        supabase_url,
        supabase_key,
        options=ClientOptions(schema=schema),
    )
    return ProductRepository(client)


def get_product_repository(client: Client) -> ProductRepository:
    """ProductRepository 인스턴스 생성."""
    return ProductRepository(client)
