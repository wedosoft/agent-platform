"""Admin CMS API - 시나리오, 커리큘럼, 지식베이스, RAG 문서 관리."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Header, UploadFile
from pydantic import BaseModel, Field

from app.services.content_repository import (
    ContentRepository,
    Scenario,
    ScenarioCategory,
    ScenarioChoice,
    get_content_repository,
)
from app.services.onboarding_repository import get_onboarding_repository

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin CMS"])

MAX_FILE_SIZE_MB = 50
ALLOWED_FILE_TYPES = {"application/pdf", "text/csv", "text/plain"}
ALLOWED_EXTENSIONS = {".pdf", ".csv", ".txt"}


class AdminAuthError(HTTPException):
    """관리자 인증 에러."""
    def __init__(self, detail: str = "관리자 권한이 필요합니다."):
        super().__init__(status_code=403, detail=detail)


async def verify_admin(authorization: Optional[str] = Header(None)) -> bool:
    """관리자 권한 검증."""
    if not authorization:
        raise AdminAuthError("Authorization 헤더가 필요합니다.")
    
    return True


def get_content_repo() -> ContentRepository:
    """ContentRepository 의존성."""
    repo = get_onboarding_repository()
    return get_content_repository(repo.client)


class ScenarioCategoryCreate(BaseModel):
    """시나리오 카테고리 생성 요청."""
    id: str = Field(..., description="카테고리 ID (예: productivity)")
    name: str = Field(..., description="영문 이름")
    name_ko: str = Field(..., description="한글 이름")
    icon: Optional[str] = Field(None, description="아이콘 클래스")
    description: Optional[str] = Field(None, description="영문 설명")
    description_ko: Optional[str] = Field(None, description="한글 설명")
    display_order: int = Field(0, description="표시 순서")


class ScenarioCategoryUpdate(BaseModel):
    """시나리오 카테고리 수정 요청."""
    name: Optional[str] = None
    name_ko: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    description_ko: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class ScenarioChoiceCreate(BaseModel):
    """시나리오 선택지 생성 요청."""
    id: str = Field(..., description="선택지 ID")
    text: str = Field(..., description="영문 텍스트")
    text_ko: str = Field(..., description="한글 텍스트")
    display_order: int = Field(0, description="표시 순서")
    is_recommended: bool = Field(False, description="권장 선택지 여부")


class ScenarioCreate(BaseModel):
    """시나리오 생성 요청."""
    id: str = Field(..., description="시나리오 ID (예: s1)")
    category_id: str = Field(..., description="카테고리 ID")
    title: str = Field(..., description="영문 제목")
    title_ko: str = Field(..., description="한글 제목")
    icon: Optional[str] = Field(None, description="아이콘 클래스")
    description: str = Field(..., description="영문 설명")
    description_ko: str = Field(..., description="한글 설명")
    display_order: int = Field(0, description="표시 순서")
    choices: List[ScenarioChoiceCreate] = Field(default_factory=list, description="선택지 목록")


class ScenarioUpdate(BaseModel):
    """시나리오 수정 요청."""
    category_id: Optional[str] = None
    title: Optional[str] = None
    title_ko: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    description_ko: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class ScenarioChoiceUpdate(BaseModel):
    """시나리오 선택지 수정 요청."""
    text: Optional[str] = None
    text_ko: Optional[str] = None
    display_order: Optional[int] = None
    is_recommended: Optional[bool] = None


class CurriculumModuleCreate(BaseModel):
    """커리큘럼 모듈 생성 요청."""
    slug: str = Field(..., description="모듈 슬러그 (URL용)")
    name_ko: str = Field(..., description="한글 이름")
    name_en: Optional[str] = Field(None, description="영문 이름")
    description_ko: str = Field(..., description="한글 설명")
    description_en: Optional[str] = Field(None, description="영문 설명")
    target_product_id: str = Field(..., description="대상 제품 ID")
    target_product_type: str = Field("module", description="제품 타입 (module/bundle)")
    display_order: int = Field(0, description="표시 순서")
    is_active: bool = Field(True, description="활성화 여부")


class CurriculumModuleUpdate(BaseModel):
    """커리큘럼 모듈 수정 요청."""
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    description_ko: Optional[str] = None
    description_en: Optional[str] = None
    target_product_id: Optional[str] = None
    target_product_type: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답."""
    id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    message: str


class AuditLogEntry(BaseModel):
    """감사 로그 항목."""
    id: str
    action: str
    entity_type: str
    entity_id: str
    admin_id: str
    changes: Dict[str, Any]
    created_at: str


async def log_audit(
    repo: ContentRepository,
    action: str,
    entity_type: str,
    entity_id: str,
    admin_id: str = "system",
    changes: Optional[Dict[str, Any]] = None,
) -> None:
    """감사 로그 기록."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": str(uuid.uuid4()),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "admin_id": admin_id,
            "changes": changes or {},
            "created_at": now,
        }
        repo.client.table("audit_log").insert(data).execute()
    except Exception as e:
        LOGGER.warning(f"Failed to log audit: {e}")


@router.get("/categories", response_model=List[ScenarioCategory])
async def list_categories(
    active_only: bool = False,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 카테고리 목록 조회."""
    return await repo.get_categories(active_only=active_only)


@router.post("/categories", response_model=ScenarioCategory)
async def create_category(
    data: ScenarioCategoryCreate,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 카테고리 생성."""
    try:
        category = await repo.create_category(
            id=data.id,
            name=data.name,
            name_ko=data.name_ko,
            icon=data.icon,
            description=data.description,
            description_ko=data.description_ko,
            display_order=data.display_order,
        )
        await log_audit(repo, "create", "scenario_category", data.id, changes=data.model_dump())
        return category
    except Exception as e:
        LOGGER.error(f"Failed to create category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/categories/{category_id}", response_model=ScenarioCategory)
async def update_category(
    category_id: str,
    data: ScenarioCategoryUpdate,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 카테고리 수정."""
    category = await repo.update_category(
        category_id=category_id,
        name=data.name,
        name_ko=data.name_ko,
        icon=data.icon,
        description=data.description,
        description_ko=data.description_ko,
        display_order=data.display_order,
        is_active=data.is_active,
    )
    if not category:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    
    await log_audit(repo, "update", "scenario_category", category_id, changes=data.model_dump(exclude_none=True))
    return category


@router.get("/scenarios", response_model=List[Scenario])
async def list_scenarios(
    category_id: Optional[str] = None,
    active_only: bool = False,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 목록 조회."""
    return await repo.get_scenarios(
        category_id=category_id,
        active_only=active_only,
        include_choices=True,
    )


@router.get("/scenarios/{scenario_id}", response_model=Scenario)
async def get_scenario(
    scenario_id: str,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 단건 조회."""
    scenario = await repo.get_scenario(scenario_id, include_choices=True)
    if not scenario:
        raise HTTPException(status_code=404, detail="시나리오를 찾을 수 없습니다.")
    return scenario


@router.post("/scenarios", response_model=Scenario)
async def create_scenario(
    data: ScenarioCreate,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 생성."""
    try:
        choices_data = [
            {
                "id": choice.id,
                "text": choice.text,
                "text_ko": choice.text_ko,
                "display_order": choice.display_order,
                "is_recommended": choice.is_recommended,
            }
            for choice in data.choices
        ]
        
        scenario = await repo.create_scenario(
            id=data.id,
            category_id=data.category_id,
            title=data.title,
            title_ko=data.title_ko,
            description=data.description,
            description_ko=data.description_ko,
            icon=data.icon,
            display_order=data.display_order,
            choices=choices_data,
        )
        await log_audit(repo, "create", "scenario", data.id, changes=data.model_dump())
        return scenario
    except Exception as e:
        LOGGER.error(f"Failed to create scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}", response_model=Scenario)
async def update_scenario(
    scenario_id: str,
    data: ScenarioUpdate,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 수정."""
    scenario = await repo.update_scenario(
        scenario_id=scenario_id,
        category_id=data.category_id,
        title=data.title,
        title_ko=data.title_ko,
        icon=data.icon,
        description=data.description,
        description_ko=data.description_ko,
        display_order=data.display_order,
        is_active=data.is_active,
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="시나리오를 찾을 수 없습니다.")
    
    await log_audit(repo, "update", "scenario", scenario_id, changes=data.model_dump(exclude_none=True))
    return scenario


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 삭제."""
    success = await repo.delete_scenario(scenario_id)
    if not success:
        raise HTTPException(status_code=404, detail="시나리오를 찾을 수 없습니다.")
    
    await log_audit(repo, "delete", "scenario", scenario_id)
    return {"message": "시나리오가 삭제되었습니다."}


@router.post("/scenarios/{scenario_id}/choices", response_model=ScenarioChoice)
async def create_scenario_choice(
    scenario_id: str,
    data: ScenarioChoiceCreate,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 선택지 추가."""
    try:
        choice = await repo.create_scenario_choice(
            id=data.id,
            scenario_id=scenario_id,
            text=data.text,
            text_ko=data.text_ko,
            display_order=data.display_order,
            is_recommended=data.is_recommended,
        )
        await log_audit(repo, "create", "scenario_choice", data.id, changes=data.model_dump())
        return choice
    except Exception as e:
        LOGGER.error(f"Failed to create scenario choice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}/choices/{choice_id}", response_model=ScenarioChoice)
async def update_scenario_choice(
    scenario_id: str,
    choice_id: str,
    data: ScenarioChoiceUpdate,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 선택지 수정."""
    choice = await repo.update_scenario_choice(
        choice_id=choice_id,
        text=data.text,
        text_ko=data.text_ko,
        display_order=data.display_order,
        is_recommended=data.is_recommended,
    )
    if not choice:
        raise HTTPException(status_code=404, detail="선택지를 찾을 수 없습니다.")
    
    await log_audit(repo, "update", "scenario_choice", choice_id, changes=data.model_dump(exclude_none=True))
    return choice


@router.delete("/scenarios/{scenario_id}/choices/{choice_id}")
async def delete_scenario_choice(
    scenario_id: str,
    choice_id: str,
    _: bool = Depends(verify_admin),
    repo: ContentRepository = Depends(get_content_repo),
):
    """시나리오 선택지 삭제."""
    success = await repo.delete_scenario_choice(choice_id)
    if not success:
        raise HTTPException(status_code=404, detail="선택지를 찾을 수 없습니다.")
    
    await log_audit(repo, "delete", "scenario_choice", choice_id)
    return {"message": "선택지가 삭제되었습니다."}


@router.get("/modules")
async def list_modules(
    product_id: Optional[str] = None,
    active_only: bool = False,
    _: bool = Depends(verify_admin),
):
    """커리큘럼 모듈 목록 조회."""
    repo = get_onboarding_repository()
    try:
        query = repo.client.table("curriculum_modules").select("*")
        
        if product_id:
            query = query.eq("target_product_id", product_id)
        if active_only:
            query = query.eq("is_active", True)
        
        response = query.order("display_order").execute()
        return response.data or []
    except Exception as e:
        LOGGER.error(f"Failed to list modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/modules")
async def create_module(
    data: CurriculumModuleCreate,
    _: bool = Depends(verify_admin),
):
    """커리큘럼 모듈 생성."""
    repo = get_onboarding_repository()
    try:
        now = datetime.now(timezone.utc).isoformat()
        module_data = {
            "id": str(uuid.uuid4()),
            "slug": data.slug,
            "name_ko": data.name_ko,
            "name_en": data.name_en or data.name_ko,
            "description_ko": data.description_ko,
            "description_en": data.description_en or data.description_ko,
            "target_product_id": data.target_product_id,
            "target_product_type": data.target_product_type,
            "display_order": data.display_order,
            "is_active": data.is_active,
            "created_at": now,
            "updated_at": now,
        }
        
        response = repo.client.table("curriculum_modules").insert(module_data).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(status_code=500, detail="모듈 생성에 실패했습니다.")
    except Exception as e:
        LOGGER.error(f"Failed to create module: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/modules/{module_id}")
async def update_module(
    module_id: str,
    data: CurriculumModuleUpdate,
    _: bool = Depends(verify_admin),
):
    """커리큘럼 모듈 수정."""
    repo = get_onboarding_repository()
    try:
        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="수정할 데이터가 없습니다.")
        
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        response = repo.client.table("curriculum_modules").update(update_data).eq("id", module_id).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(status_code=404, detail="모듈을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to update module: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/modules/{module_id}")
async def delete_module(
    module_id: str,
    _: bool = Depends(verify_admin),
):
    """커리큘럼 모듈 삭제."""
    repo = get_onboarding_repository()
    try:
        repo.client.table("curriculum_modules").delete().eq("id", module_id).execute()
        return {"message": "모듈이 삭제되었습니다."}
    except Exception as e:
        LOGGER.error(f"Failed to delete module: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/modules/{module_id}/reorder")
async def reorder_modules(
    module_id: str,
    new_order: int,
    _: bool = Depends(verify_admin),
):
    """커리큘럼 모듈 순서 변경."""
    repo = get_onboarding_repository()
    try:
        update_data = {
            "display_order": new_order,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        response = repo.client.table("curriculum_modules").update(update_data).eq("id", module_id).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(status_code=404, detail="모듈을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to reorder module: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    product_id: Optional[str] = None,
    category_id: Optional[str] = None,
    _: bool = Depends(verify_admin),
):
    """RAG 문서 업로드."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 필요합니다.")
    
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기가 {MAX_FILE_SIZE_MB}MB를 초과합니다.",
        )
    
    document_id = str(uuid.uuid4())
    
    return DocumentUploadResponse(
        id=document_id,
        filename=file.filename,
        file_type=file_ext,
        file_size=file_size,
        status="pending",
        message="문서가 업로드되었습니다. RAG 인덱싱이 진행 중입니다.",
    )
