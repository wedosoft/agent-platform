"""
커리큘럼 모듈의 부족한 섹션을 Gemini File Search로 채워 넣는 보조 스크립트.

- Supabase 스키마나 구글 스토어를 변경하지 않고, 메타데이터 필터(product/category)만 사용.
- 기본 섹션 5종(basic 레벨) 중 비어 있는 것만 생성해 `module_contents`에 저장.
- dry-run 옵션으로 생성 결과만 출력 가능.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from typing import Dict, List, Tuple

from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings
from app.models.metadata import MetadataFilter
from app.services.gemini_file_search_client import GeminiFileSearchClient, GeminiClientError

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

REQUIRED_SECTIONS: List[Tuple[str, str, str]] = [
    ("overview", "모듈 개요", "basic"),
    ("core_concepts", "핵심 개념", "basic"),
    ("features", "주요 기능", "basic"),
    ("practice", "실습 가이드", "basic"),
    ("faq", "FAQ", "basic"),
]


def _build_supabase_client(settings) -> Client:
    return create_client(
        settings.supabase_common_url,
        settings.supabase_common_service_role_key,
        options=ClientOptions(schema="onboarding"),
    )


def _build_product_filters(product_id: str, category_slug: str | None) -> List[MetadataFilter]:
    filters: List[MetadataFilter] = []
    if product_id:
        filters.append(MetadataFilter(key="product", value=product_id))
    if category_slug:
        filters.append(MetadataFilter(key="category", value=category_slug))
    return filters


async def _generate_section_text(
    fs_client: GeminiFileSearchClient,
    store: str,
    module: Dict,
    section_type: str,
    level: str,
) -> str:
    prompt = (
        f"{module.get('target_product_id')} 제품의 '{module.get('name_ko')}' 모듈에서 "
        f"{section_type} 섹션({level})을 작성하세요. "
        "제품/카테고리 메타데이터와 일치하는 문서만 사용하고, 범위를 벗어나면 오류를 반환하세요. "
        "한국어 마크다운으로 400~800자 내외로 작성하십시오."
    )

    filters = _build_product_filters(module.get("target_product_id"), module.get("kb_category_slug"))

    result = await fs_client.search(
        query=prompt,
        store_names=[store],
        metadata_filters=filters,
    )
    text = (result.get("text") or "").strip()
    return text


async def backfill(dry_run: bool = False) -> None:
    settings = get_settings()

    if not settings.gemini_store_common:
        raise RuntimeError("GEMINI 공용 스토어가 설정되어 있지 않습니다 (gemini_store_common).")

    supabase = _build_supabase_client(settings)
    fs_client = GeminiFileSearchClient(
        api_key=settings.gemini_api_key,
        primary_model=settings.gemini_primary_model,
        fallback_model=settings.gemini_fallback_model,
    )

    modules = (
        supabase.table("curriculum_modules")
        .select("id,name_ko,target_product_id,kb_category_slug,description,is_active")
        .eq("is_active", True)
        .execute()
        .data
    )

    for module in modules:
        module_id = module["id"]
        existing = (
            supabase.table("module_contents")
            .select("section_type,level")
            .eq("module_id", module_id)
            .execute()
            .data
        )
        existing_keys = {(row["section_type"], row["level"]) for row in (existing or [])}
        missing = [sec for sec in REQUIRED_SECTIONS if (sec[0], sec[2]) not in existing_keys]

        if not missing:
            continue

        LOGGER.info("Module %s: %d sections missing -> %s", module["name_ko"], len(missing), missing)

        for section_type, title_ko, level in missing:
            try:
                text = await _generate_section_text(
                    fs_client=fs_client,
                    store=settings.gemini_store_common,
                    module=module,
                    section_type=section_type,
                    level=level,
                )
            except GeminiClientError as exc:
                LOGGER.warning("Gemini 생성 실패 (%s/%s): %s", module["name_ko"], section_type, exc)
                continue

            if not text:
                LOGGER.warning("콘텐츠 없음 (%s/%s) - 건너뜀", module["name_ko"], section_type)
                continue

            row = {
                "id": str(uuid.uuid4()),
                "module_id": module_id,
                "section_type": section_type,
                "level": level,
                "title_ko": title_ko,
                "content_md": text,
                "display_order": 0,
                "estimated_minutes": 5,
                "is_active": True,
            }

            if dry_run:
                LOGGER.info("[dry-run] insert -> %s", row["title_ko"])
            else:
                supabase.table("module_contents").insert(row).execute()
                LOGGER.info("Inserted section %s for module %s", section_type, module["name_ko"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill curriculum module contents via Gemini File Search.")
    parser.add_argument("--dry-run", action="store_true", help="생성만 수행하고 DB에는 쓰지 않음")
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
