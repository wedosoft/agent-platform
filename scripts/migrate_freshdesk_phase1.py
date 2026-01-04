"""
Freshdesk Phase1 온보딩 커리큘럼 마이그레이션 스크립트

JSON 파일에서 Phase 1 온보딩 데이터를 읽어 Supabase에 삽입합니다.
기존 Freshdesk 모듈은 삭제 마이그레이션으로 제거된 상태여야 합니다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# 섹션 타입 매핑 (JSON → DB)
# DB 스키마: overview, core_concepts, features, practice, advanced, faq
# 실제 사용 예시를 보면 'concept', 'feature-guide'도 허용되는 것으로 보임
SECTION_TYPE_MAPPING: Dict[str, str] = {
    "overview": "overview",
    "concept": "core_concepts",  # JSON의 concept → DB의 core_concepts
    "feature-guide": "features",  # JSON의 feature-guide → DB의 features
    "practice": "practice",
    "knowledge-check": "faq",  # knowledge-check → faq로 매핑
    "quick-reference": "quick-reference",  # quick-reference는 그대로 유지 (VARCHAR(50)이므로 허용)
    "quiz": "faq",  # quiz 섹션도 faq로 매핑 (content_md만 있는 경우)
}

# JSON 필드명 → DB 필드명 매핑
QUIZ_FIELD_MAPPING = {
    "correct_choice_id": "correct_choice_id",  # JSON과 DB 동일
    "correct_answer": "correct_choice_id",  # JSON에 correct_answer가 있을 경우
}


def _build_supabase_client(settings) -> Client:
    """Supabase 클라이언트 생성 (onboarding 스키마)."""
    return create_client(
        settings.supabase_common_url,
        settings.supabase_common_service_role_key,
        options=ClientOptions(schema="onboarding"),
    )


def _load_json_file(json_path: Path) -> Dict[str, Any]:
    """JSON 파일 로드."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        LOGGER.error(f"JSON 파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        LOGGER.error(f"JSON 파싱 오류: {e}")
        sys.exit(1)


def _create_uuid_mappings(data: Dict[str, Any]) -> tuple[Dict[str, UUID], Dict[str, UUID]]:
    """
    UUID 매핑 테이블 생성.
    
    Returns:
        (module_id_map, section_id_map)
    """
    module_id_map: Dict[str, UUID] = {}
    section_id_map: Dict[str, UUID] = {}
    
    # 모듈 ID 매핑
    for module in data.get("modules", []):
        module_id = module.get("module_id")
        if module_id:
            module_id_map[module_id] = uuid4()
    
    # 섹션 ID 매핑
    for module in data.get("modules", []):
        module_id = module.get("module_id")
        for section in module.get("sections", []):
            section_id = section.get("section_id")
            if section_id:
                # 섹션 ID는 모듈 ID와 섹션 ID 조합으로 고유성 보장
                key = f"{module_id}::{section_id}"
                section_id_map[key] = uuid4()
    
    LOGGER.info(f"UUID 매핑 생성 완료: 모듈 {len(module_id_map)}개, 섹션 {len(section_id_map)}개")
    return module_id_map, section_id_map


def _map_prerequisite_ids(
    prerequisite_ids: List[str],
    module_id_map: Dict[str, UUID],
) -> List[str]:
    """선수 모듈 ID 배열을 UUID 배열로 변환."""
    result = []
    for pid in prerequisite_ids:
        if pid in module_id_map:
            result.append(str(module_id_map[pid]))
        else:
            LOGGER.warning(f"선수 모듈 ID를 찾을 수 없음: {pid}")
    return result


def _map_section_type(json_type: str) -> str:
    """JSON 섹션 타입을 DB 섹션 타입으로 변환."""
    return SECTION_TYPE_MAPPING.get(json_type, json_type)


async def _insert_modules(
    supabase: Client,
    data: Dict[str, Any],
    module_id_map: Dict[str, UUID],
) -> None:
    """모듈 데이터 삽입."""
    modules_to_insert = []
    
    for module in data.get("modules", []):
        module_id_str = module.get("module_id")
        if not module_id_str or module_id_str not in module_id_map:
            continue
        
        module_uuid = module_id_map[module_id_str]
        
        # slug 생성: module_slug가 없으면 module_name_en에서 자동 생성
        slug = module.get("module_slug")
        if not slug:
            # module_name_en을 기반으로 slug 생성 (소문자, 공백을 하이픈으로)
            name_en = module.get("module_name_en", "")
            if name_en:
                slug = name_en.lower().replace(" ", "-").replace("&", "and")
            else:
                # module_name_ko를 기반으로 생성
                name_ko = module.get("module_name_ko", "")
                slug = name_ko.lower().replace(" ", "-").replace("&", "and")
        
        if not slug:
            LOGGER.warning(f"모듈 {module_id_str}의 slug를 생성할 수 없습니다. module_id를 사용합니다.")
            slug = module_id_str.replace("_", "-")
        
        # 선수 모듈 ID 변환
        prerequisite_ids = _map_prerequisite_ids(
            module.get("prerequisite_module_ids", []),
            module_id_map,
        )
        
        # feature_tags는 TEXT[] 타입이므로 Python 리스트를 그대로 전달
        feature_tags_value = module.get("feature_tags", [])
        
        # 기본 모듈 데이터
        module_data = {
            "id": str(module_uuid),
            "target_product_id": "freshdesk",
            "target_product_type": "module",
            "name_ko": module.get("module_name_ko", ""),
            "name_en": module.get("module_name_en"),
            "slug": slug,
            "description": module.get("module_description"),
            "icon": "fa-book",  # 기본값
            "display_order": module.get("module_order", module.get("display_order", 0)),
            "estimated_minutes": module.get("estimated_minutes", 30),
            "learning_objectives": module.get("learning_objectives", []),  # JSONB는 Python 리스트를 직접 전달
            "content_strategy": "hybrid",
            "kb_category_slug": None,
            "is_active": True,
        }
        
        # 배열 필드는 값이 있을 때만 추가 (빈 배열이면 기본값 '{}' 사용)
        # Supabase Python 클라이언트가 빈 배열을 문자열 "[]"로 변환하는 문제 방지
        if prerequisite_ids:
            module_data["prerequisite_module_ids"] = prerequisite_ids  # UUID 배열 (Python 리스트)
        
        if feature_tags_value:
            module_data["feature_tags"] = feature_tags_value  # TEXT[] 배열 (Python 리스트)
        modules_to_insert.append(module_data)
    
    if modules_to_insert:
        # UPSERT 사용: (target_product_id, slug) 유니크 제약 때문에
        for module_data in modules_to_insert:
            supabase.table("curriculum_modules").upsert(
                module_data,
                on_conflict="target_product_id,slug"
            ).execute()
        LOGGER.info(f"✅ 모듈 {len(modules_to_insert)}개 삽입 완료")
    else:
        LOGGER.warning("삽입할 모듈이 없습니다.")


async def _insert_sections(
    supabase: Client,
    data: Dict[str, Any],
    module_id_map: Dict[str, UUID],
    section_id_map: Dict[str, UUID],
) -> None:
    """섹션 콘텐츠 삽입."""
    sections_to_insert = []
    
    for module in data.get("modules", []):
        module_id_str = module.get("module_id")
        if not module_id_str or module_id_str not in module_id_map:
            continue
        
        module_uuid = module_id_map[module_id_str]
        
        for idx, section in enumerate(module.get("sections", [])):
            section_id_str = section.get("section_id")
            if not section_id_str:
                continue
            
            section_key = f"{module_id_str}::{section_id_str}"
            if section_key not in section_id_map:
                continue
            
            section_uuid = section_id_map[section_key]
            json_section_type = section.get("section_type", "")
            db_section_type = _map_section_type(json_section_type)
            
            # level은 JSON에 없으면 'basic' 기본값
            level = section.get("level", "basic")
            
            section_data = {
                "id": str(section_uuid),
                "module_id": str(module_uuid),
                "section_type": db_section_type,
                "level": level,
                "title_ko": section.get("title_ko", ""),
                "title_en": section.get("title_en"),
                "content_md": section.get("content_md", ""),
                "display_order": section.get("section_order", idx + 1),
                "estimated_minutes": section.get("estimated_minutes", 5),
                "is_active": True,
            }
            sections_to_insert.append(section_data)
    
    if sections_to_insert:
        # 유니크 제약 (module_id, section_type, level) 때문에 개별 UPSERT 사용
        # 같은 section_type과 level이 여러 개 있을 수 있으므로
        inserted_count = 0
        for section_data in sections_to_insert:
            try:
                # UPSERT: ON CONFLICT DO UPDATE
                supabase.table("module_contents").upsert(
                    section_data,
                    on_conflict="module_id,section_type,level"
                ).execute()
                inserted_count += 1
            except Exception as e:
                LOGGER.warning(f"섹션 삽입 실패 (무시하고 계속): {section_data.get('title_ko', 'unknown')} - {e}")
        LOGGER.info(f"✅ 섹션 {inserted_count}개 삽입 완료")
    else:
        LOGGER.warning("삽입할 섹션이 없습니다.")


async def _insert_quizzes(
    supabase: Client,
    data: Dict[str, Any],
    module_id_map: Dict[str, UUID],
) -> None:
    """
    퀴즈 데이터 삽입.
    
    모듈 1~2: section_type "knowledge-check"의 quiz_questions 배열 사용
    모듈 3~4: section_type "quiz"의 content_md는 파싱하지 않고 건너뜀 (AI 생성 폴백)
    """
    quizzes_to_insert = []
    
    for module in data.get("modules", []):
        module_id_str = module.get("module_id")
        if not module_id_str or module_id_str not in module_id_map:
            continue
        
        module_uuid = module_id_map[module_id_str]
        
        for section in module.get("sections", []):
            section_type = section.get("section_type", "")
            
            # knowledge-check 섹션의 quiz_questions 배열 처리
            if section_type == "knowledge-check" and section.get("quiz_questions"):
                level = section.get("level", "basic")
                
                for idx, quiz in enumerate(section.get("quiz_questions", [])):
                    # correct_answer 또는 correct_choice_id 필드 확인
                    correct_choice_id = quiz.get("correct_choice_id") or quiz.get("correct_answer")
                    if not correct_choice_id:
                        LOGGER.warning(f"퀴즈에 정답이 없습니다: {quiz.get('question_id', 'unknown')}")
                        continue
                    
                    quiz_data = {
                        "id": str(uuid4()),
                        "module_id": str(module_uuid),
                        "difficulty": level,
                        "question_order": idx + 1,
                        "question": quiz.get("question", ""),
                        "context": quiz.get("context"),
                        "choices": quiz.get("choices", []),  # JSONB는 Python 리스트/딕셔너리를 직접 전달 가능
                        "correct_choice_id": correct_choice_id,
                        "explanation": quiz.get("explanation", ""),
                        "learning_point": quiz.get("learning_point"),
                        "related_doc_url": None,
                        "quality_rating": None,
                        "is_verified": False,
                        "reviewed_by": None,
                        "reviewed_at": None,
                        "is_active": True,
                    }
                    quizzes_to_insert.append(quiz_data)
            
            # quiz 섹션은 content_md만 있고 객관식 퀴즈가 없으므로 건너뜀
            # (AI 생성 폴백에 맡김)
            elif section_type == "quiz":
                LOGGER.info(
                    f"모듈 {module_id_str}의 quiz 섹션은 content_md만 있어 퀴즈 삽입을 건너뜁니다. "
                    "AI 생성 폴백을 사용하세요."
                )
    
    if quizzes_to_insert:
        supabase.table("quiz_questions").insert(quizzes_to_insert).execute()
        LOGGER.info(f"✅ 퀴즈 {len(quizzes_to_insert)}개 삽입 완료")
    else:
        LOGGER.warning("삽입할 퀴즈가 없습니다.")


async def migrate(dry_run: bool = False, json_path: Optional[Path] = None) -> None:
    """마이그레이션 실행."""
    settings = get_settings()
    
    # JSON 파일 경로 결정
    if json_path is None:
        # 기본 경로: onboarding 저장소의 docs/curriculum-v2/
        # agent-platform과 onboarding은 같은 상위 디렉토리에 있다고 가정
        default_path = Path(__file__).parent.parent.parent / "onboarding" / "docs" / "curriculum-v2" / "freshdesk_phase1_onboarding_COMPLETE.json"
        if default_path.exists():
            json_path = default_path
        else:
            # 절대 경로 시도 (macOS/Linux)
            json_path = Path("/Users/alan/GitHub/onboarding/docs/curriculum-v2/freshdesk_phase1_onboarding_COMPLETE.json")
            if not json_path.exists():
                # Windows 경로 시도
                json_path = Path("C:/Users/alan/GitHub/onboarding/docs/curriculum-v2/freshdesk_phase1_onboarding_COMPLETE.json")
    
    if not json_path.exists():
        LOGGER.error(f"JSON 파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)
    
    LOGGER.info(f"JSON 파일 로드: {json_path}")
    data = _load_json_file(json_path)
    
    LOGGER.info(f"Phase: {data.get('phase_info', {}).get('phase_name', 'Unknown')}")
    LOGGER.info(f"모듈 수: {data.get('phase_info', {}).get('total_modules', 0)}")
    
    # UUID 매핑 생성
    module_id_map, section_id_map = _create_uuid_mappings(data)
    
    if dry_run:
        LOGGER.info("=== DRY RUN 모드 ===")
        LOGGER.info(f"삽입 예정: 모듈 {len(module_id_map)}개, 섹션 {len(section_id_map)}개")
        return
    
    # Supabase 연결
    supabase = _build_supabase_client(settings)
    
    # 데이터 삽입 (순서 중요: 모듈 → 섹션 → 퀴즈)
    try:
        await _insert_modules(supabase, data, module_id_map)
        await _insert_sections(supabase, data, module_id_map, section_id_map)
        await _insert_quizzes(supabase, data, module_id_map)
        
        LOGGER.info("✅ 마이그레이션 완료!")
    except Exception as e:
        LOGGER.error(f"마이그레이션 실패: {e}", exc_info=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freshdesk Phase1 온보딩 커리큘럼 마이그레이션"
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        help="JSON 파일 경로 (기본값: onboarding/docs/curriculum-v2/freshdesk_phase1_onboarding_COMPLETE.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 삽입 없이 검증만 수행",
    )
    args = parser.parse_args()
    
    asyncio.run(migrate(dry_run=args.dry_run, json_path=args.json_path))


if __name__ == "__main__":
    main()

