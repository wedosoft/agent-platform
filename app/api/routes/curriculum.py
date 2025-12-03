"""커리큘럼 API 라우터."""

import json
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.curriculum import (
    CurriculumModule,
    CurriculumModuleResponse,
    QuizQuestion,
    QuizSubmitRequest,
    QuizSubmitResponse,
    ModuleProgress,
    UpdateProgressRequest,
    ProgressSummary,
)
from app.services.curriculum_repository import (
    get_curriculum_repository,
    CurriculumRepositoryError,
)
from app.services.gemini_file_search_client import GeminiFileSearchClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/curriculum", tags=["curriculum"])


def _get_settings():
    """설정 가져오기."""
    return get_settings()


def _get_file_search_client() -> GeminiFileSearchClient:
    """GeminiFileSearchClient 인스턴스 생성."""
    settings = _get_settings()
    return GeminiFileSearchClient(
        api_key=settings.gemini_api_key,
        primary_model=settings.gemini_primary_model,
        fallback_model=settings.gemini_fallback_model,
    )


# ============================================
# SSE 헬퍼
# ============================================

def format_sse(event: str, data: dict) -> str:
    """SSE 포맷으로 변환."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================
# 모듈 조회
# ============================================

@router.get("/modules", response_model=List[CurriculumModule])
async def get_modules(
    session_id: str = Query(..., alias="sessionId", description="세션 ID"),
    product: str = Query("freshservice", description="제품 ID"),
):
    """
    커리큘럼 모듈 목록 조회.
    
    - 각 모듈의 기본 정보 반환
    """
    try:
        repo = get_curriculum_repository()
        modules = await repo.get_modules(product=product)
        return modules
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get modules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/{module_id}", response_model=CurriculumModule)
async def get_module(
    module_id: UUID = Path(..., description="모듈 ID"),
):
    """모듈 상세 조회."""
    try:
        repo = get_curriculum_repository()
        module = await repo.get_module_by_id(module_id)
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        return module
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get module: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 학습 콘텐츠 스트리밍 (RAG 기반)
# ============================================

@router.get("/modules/{module_id}/learn/stream")
async def stream_learning_content(
    module_id: UUID = Path(..., description="모듈 ID"),
    session_id: str = Query(..., alias="sessionId", description="세션 ID"),
):
    """
    모듈 학습 콘텐츠 스트리밍 (RAG 기반).
    
    - RAG 스토어에서 모듈 관련 콘텐츠 검색
    - 스트리밍 응답으로 학습 콘텐츠 제공
    - 학습 시작 시 진도 기록
    """
    repo = get_curriculum_repository()
    
    # 모듈 조회
    module = await repo.get_module_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # 학습 시작 기록
    await repo.start_learning(session_id, module_id)
    
    async def event_generator():
        try:
            settings = _get_settings()
            store_product = settings.gemini_store_common
            
            # RAG 검색 쿼리 구성
            query = f"""Freshservice {module.name_ko}에 대해 자세히 설명해주세요.

다음 내용을 포함해서 구조화된 학습 콘텐츠를 제공해주세요:
1. 개요 및 핵심 개념
2. 주요 기능과 사용법
3. 실무 활용 팁
4. 자주 묻는 질문

{module.description or ''}

한국어로 마크다운 형식으로 답변해주세요."""

            # RAG 스토어 검색
            rag_stores = []
            if store_product:
                rag_stores.append(store_product)
            
            if not rag_stores:
                yield format_sse("error", {"message": "RAG store not configured"})
                return
            
            # 스트리밍 생성
            client = _get_file_search_client()
            
            full_response = ""
            async for chunk in client.stream_search(
                query=query,
                store_names=rag_stores,
                system_instruction=f"당신은 Freshservice {module.name_ko} 전문 교육 강사입니다. 신입사원이 이해하기 쉽도록 명확하고 구체적인 설명을 제공하세요.",
            ):
                event_type = chunk.get("event")
                data = chunk.get("data", {})
                
                if event_type == "status":
                    yield format_sse("status", data)
                elif event_type == "result":
                    text = data.get("text", "")
                    if text:
                        full_response = text
                        yield format_sse("chunk", {"text": text})
                        yield format_sse("result", {"text": text})
                elif event_type == "error":
                    yield format_sse("error", data)
            
            if not full_response:
                yield format_sse("error", {"message": "콘텐츠를 생성하지 못했습니다."})
            
        except Exception as e:
            logger.error(f"Learning content stream error: {e}")
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/modules/{module_id}/section/stream")
async def stream_section_content(
    module_id: UUID = Path(..., description="모듈 ID"),
    session_id: str = Query(..., alias="sessionId", description="세션 ID"),
    section_id: str = Query(..., alias="sectionId", description="섹션 ID"),
    section_prompt: str = Query(..., alias="sectionPrompt", description="섹션 프롬프트"),
):
    """
    모듈 섹션별 학습 콘텐츠 스트리밍 (RAG 기반).
    
    - 개요, 주요 기능, 실무 활용, FAQ 등 섹션별로 콘텐츠 생성
    - 짧고 집중된 콘텐츠로 학습 효율 향상
    """
    repo = get_curriculum_repository()
    
    # 모듈 조회
    module = await repo.get_module_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    async def event_generator():
        try:
            settings = _get_settings()
            store_product = settings.gemini_store_common
            
            # RAG 검색 쿼리 구성
            query = f"""Freshservice {module.name_ko}에 대해 다음 요청에 맞게 답변해주세요.

{section_prompt}

컨텍스트: {module.description or ''}"""

            # RAG 스토어 검색
            rag_stores = []
            if store_product:
                rag_stores.append(store_product)
            
            if not rag_stores:
                yield format_sse("error", {"message": "RAG store not configured"})
                return
            
            # 스트리밍 생성
            client = _get_file_search_client()
            
            async for chunk in client.stream_search(
                query=query,
                store_names=rag_stores,
                system_instruction=f"당신은 Freshservice {module.name_ko} 전문 교육 강사입니다. 신입사원이 이해하기 쉽도록 명확하고 구체적인 설명을 제공하세요. 요청된 분량을 준수하세요.",
            ):
                event_type = chunk.get("event")
                data = chunk.get("data", {})
                
                if event_type == "status":
                    yield format_sse("status", data)
                elif event_type == "result":
                    text = data.get("text", "")
                    if text:
                        yield format_sse("chunk", {"text": text})
                        yield format_sse("result", {"text": text})
                elif event_type == "error":
                    yield format_sse("error", data)
            
        except Exception as e:
            logger.error(f"Section content stream error: {e}")
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================
# AI 멘토 채팅 (모듈 컨텍스트 인식)
# ============================================

# 모듈별 대화 히스토리 캐시
_module_chat_cache: dict = {}


@router.get("/modules/{module_id}/chat/stream")
async def stream_module_chat(
    module_id: UUID = Path(..., description="모듈 ID"),
    session_id: str = Query(..., alias="sessionId", description="세션 ID"),
    query: str = Query(..., description="질문"),
):
    """
    모듈 컨텍스트 인식 AI 멘토 채팅.
    
    - 현재 학습 중인 모듈에 맞춤화된 답변 제공
    - RAG 검색으로 관련 문서 참조
    - 대화 히스토리 유지
    """
    repo = get_curriculum_repository()
    
    # 모듈 조회
    module = await repo.get_module_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # 대화 히스토리 조회
    cache_key = f"{session_id}:{module_id}"
    history = _module_chat_cache.get(cache_key, [])
    
    async def event_generator():
        try:
            settings = _get_settings()
            store_product = settings.gemini_store_common
            
            # 시스템 프롬프트 (모듈 컨텍스트 포함)
            system_prompt = f"""당신은 Freshservice {module.name_ko} 전문 교육 멘토입니다.

현재 학습 모듈: {module.name_ko} ({module.name_en or ''})
모듈 설명: {module.description or ''}

당신의 역할:
- 신입사원의 {module.name_ko} 관련 질문에 명확하고 실용적인 답변 제공
- Freshservice 공식 문서와 베스트 프랙티스 기반 설명
- 실무에서 바로 활용할 수 있는 구체적인 예시 제공
- 이해를 돕기 위한 단계별 가이드 제공

답변 스타일:
- 간결하고 본론 중심 (인사말 생략)
- 한국어로 답변
- 마크다운 형식 사용"""

            # RAG 스토어 검색
            rag_stores = []
            if store_product:
                rag_stores.append(store_product)
            
            # 스트리밍 생성
            client = _get_file_search_client()
            
            full_response = ""
            async for chunk in client.stream_search(
                query=query,
                store_names=rag_stores,
                conversation_history=history[-4:],  # 최근 4턴
                system_instruction=system_prompt,
            ):
                if chunk.get("text"):
                    text = chunk["text"]
                    full_response += text
                    yield format_sse("chunk", {"text": text})
            
            # 히스토리 업데이트
            history.append({"user": query, "model": full_response})
            _module_chat_cache[cache_key] = history[-10:]  # 최근 10턴만 유지
            
            yield format_sse("result", {"text": full_response})
            
        except Exception as e:
            logger.error(f"Module chat stream error: {e}")
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================
# 퀴즈 문제 조회
# ============================================

@router.get("/modules/{module_id}/questions", response_model=List[QuizQuestion])
async def get_questions(
    module_id: UUID = Path(..., description="모듈 ID"),
    difficulty: str = Query(..., description="난이도 (basic, advanced)"),
):
    """
    모듈별 퀴즈 문제 조회.
    
    - 정답은 포함되지 않음
    - difficulty: basic(기초), advanced(심화)
    """
    if difficulty not in ("basic", "advanced"):
        raise HTTPException(
            status_code=400,
            detail="difficulty must be 'basic' or 'advanced'"
        )
    
    try:
        repo = get_curriculum_repository()
        questions = await repo.get_questions(
            module_id=module_id,
            difficulty=difficulty,
        )
        return questions
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 퀴즈 제출
# ============================================

@router.post("/modules/{module_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    module_id: UUID = Path(..., description="모듈 ID"),
    request: QuizSubmitRequest = None,  # type: ignore
):
    """
    퀴즈 제출 및 채점.
    
    - 80점 이상 통과
    - 기초 퀴즈 통과 후 심화 퀴즈 도전 가능
    - 기초 + 심화 모두 통과 시 모듈 완료
    """
    if not request:
        raise HTTPException(status_code=400, detail="Request body is required")
    
    if request.difficulty not in ("basic", "advanced"):
        raise HTTPException(
            status_code=400,
            detail="difficulty must be 'basic' or 'advanced'"
        )
    
    if str(module_id) != str(request.module_id):
        raise HTTPException(
            status_code=400,
            detail="module_id in path and body must match"
        )
    
    try:
        repo = get_curriculum_repository()
        result = await repo.submit_quiz(
            session_id=request.session_id,
            module_id=module_id,
            difficulty=request.difficulty,
            answers=request.answers,
            started_at=request.started_at,
        )
        return result
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to submit quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 진도 관리
# ============================================

@router.get("/progress", response_model=ProgressSummary)
async def get_progress_summary(
    session_id: str = Query(..., alias="sessionId", description="세션 ID"),
    product: str = Query("freshservice", description="제품 ID"),
):
    """
    전체 학습 진도 요약.
    
    - 모듈별 진도 상태
    - 전체 완료율
    """
    try:
        repo = get_curriculum_repository()
        modules = await repo.get_modules_with_progress(
            session_id=session_id,
            product=product,
        )
        
        total = len(modules)
        completed = sum(1 for m in modules if m.status == "completed")
        in_progress = sum(1 for m in modules if m.status in ("learning", "quiz_ready"))
        
        return ProgressSummary(
            sessionId=session_id,
            totalModules=total,
            completedModules=completed,
            inProgressModules=in_progress,
            completionRate=round(completed / total * 100, 1) if total > 0 else 0,
            modules=modules,
        )
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get progress summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules/{module_id}/progress", response_model=ModuleProgress)
async def get_module_progress(
    module_id: UUID = Path(..., description="모듈 ID"),
    session_id: str = Query(..., alias="sessionId", description="세션 ID"),
):
    """모듈별 상세 진도 조회."""
    try:
        repo = get_curriculum_repository()
        progress = await repo.get_progress(session_id, module_id)
        
        if not progress:
            # 진도 없으면 기본값 반환
            return ModuleProgress(
                sessionId=session_id,
                moduleId=module_id,
                status="not_started",
                learningStartedAt=None,
                learningCompletedAt=None,
                basicQuizScore=None,
                basicQuizPassed=False,
                basicQuizAttempts=0,
                advancedQuizScore=None,
                advancedQuizPassed=False,
                advancedQuizAttempts=0,
                completedAt=None,
            )
        return progress
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get module progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/modules/{module_id}/progress", response_model=ModuleProgress)
async def update_module_progress(
    module_id: UUID = Path(..., description="모듈 ID"),
    request: UpdateProgressRequest = None,  # type: ignore
):
    """
    모듈 진도 업데이트.
    
    - 학습 완료 표시
    - 상태 변경
    """
    if not request:
        raise HTTPException(status_code=400, detail="Request body is required")
    
    try:
        repo = get_curriculum_repository()
        progress = await repo.update_progress(
            session_id=request.session_id,
            module_id=module_id,
            status=request.status,
            learning_completed=request.learning_completed,
        )
        
        if not progress:
            raise HTTPException(status_code=500, detail="Failed to update progress")
        return progress
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to update module progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))
