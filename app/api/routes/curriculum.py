"""커리큘럼 API 라우터."""

import json
import logging
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.curriculum import (
    CurriculumModule,
    CurriculumModuleResponse,
    QuizQuestion,
    QuizChoice,
    QuizSubmitRequest,
    QuizSubmitResponse,
    ModuleProgress,
    UpdateProgressRequest,
    ProgressSummary,
    ModuleContent,
    ModuleContentResponse,
)
from app.services.curriculum_repository import (
    get_curriculum_repository,
    CurriculumRepositoryError,
)
from app.services.gemini_file_search_client import GeminiFileSearchClient
from app.services.gemini_client import get_gemini_client
from app.models.metadata import MetadataFilter
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


# ============================================
# 모듈 콘텐츠 조회 (정적 콘텐츠 - DB에서 로드)
# ============================================

@router.get("/modules/{module_id}/contents", response_model=ModuleContentResponse)
async def get_module_contents(
    module_id: UUID = Path(..., description="모듈 ID"),
    level: Optional[str] = Query(None, description="난이도 필터 (basic, intermediate, advanced)"),
):
    """
    모듈의 정적 학습 콘텐츠 조회.
    
    - DB에 저장된 콘텐츠를 즉시 반환 (LLM 지연 없음)
    - 난이도별 (기초/중급/고급) 콘텐츠 제공
    - 각 섹션: 개요, 핵심 개념, 기능, 실습, FAQ
    """
    try:
        repo = get_curriculum_repository()
        contents = await repo.get_module_contents(module_id, level)
        return contents
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get module contents: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/modules/{module_id}/contents/{section_type}", response_model=ModuleContent)
async def get_section_content(
    module_id: UUID = Path(..., description="모듈 ID"),
    section_type: str = Path(..., description="섹션 타입 (overview, core_concepts, features, practice, faq)"),
    level: str = Query("basic", description="난이도 (basic, intermediate, advanced)"),
):
    """
    특정 섹션의 콘텐츠 조회.
    
    - 한 섹션만 필요할 때 사용
    - 콘텐츠가 없으면 404 반환
    """
    try:
        repo = get_curriculum_repository()
        content = await repo.get_section_content(module_id, section_type, level)
        if not content:
            raise HTTPException(
                status_code=404, 
                detail=f"Content not found for section '{section_type}' at level '{level}'"
            )
        return content
    except CurriculumRepositoryError as e:
        logger.error(f"Failed to get section content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 모듈 섹션 콘텐츠 스트리밍 (LLM 기반 - 폴백/채팅용)
# ============================================

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
    - 정적 콘텐츠가 없을 때 폴백으로 사용
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
            
            # 제품명 매핑 (targetProductId -> 표시명, RAG 필터값)
            product_id = module.target_product_id or "freshworks"
            product_display_names = {
                "freshdesk": "Freshdesk",
                "freshdesk-omni": "Freshdesk Omni",
                "freshchat": "Freshchat",
                "freshsales": "Freshsales",
                "freshservice": "Freshservice",
            }
            # RAG 필터용 제품값 (freshdesk-omni와 freshchat은 freshdesk로 통합 검색)
            product_rag_filters = {
                "freshdesk": ["freshdesk"],
                "freshdesk-omni": ["freshdesk", "freshchat"],
                "freshchat": ["freshdesk", "freshchat"],
                "freshsales": ["freshsales"],
                "freshservice": ["freshservice"],
            }
            
            product_name = product_display_names.get(product_id, "Freshworks")
            rag_product_values = product_rag_filters.get(product_id, [product_id])
            
            # 시스템 프롬프트 (모듈 컨텍스트 포함)
            system_prompt = f"""당신은 {product_name} {module.name_ko} 전문 교육 멘토입니다.

현재 학습 제품: {product_name}
현재 학습 모듈: {module.name_ko} ({module.name_en or ''})
모듈 설명: {module.description or ''}

당신의 역할:
- 신입사원의 {product_name} {module.name_ko} 관련 질문에 명확하고 실용적인 답변 제공
- {product_name} 공식 문서와 베스트 프랙티스 기반 설명
- 실무에서 바로 활용할 수 있는 구체적인 예시 제공
- 이해를 돕기 위한 단계별 가이드 제공

중요: 반드시 {product_name} 제품에 대해서만 답변하세요. 다른 Freshworks 제품(예: Freshservice, Freshsales 등)의 내용을 혼동하지 마세요.

답변 스타일:
- 간결하고 본론 중심 (인사말 생략)
- 한국어로 답변
- 마크다운 형식 사용"""

            # RAG 스토어 및 메타데이터 필터
            rag_stores = []
            if store_product:
                rag_stores.append(store_product)
            
            # 제품별 메타데이터 필터 생성 (IN 연산자로 OR 처리)
            metadata_filters = None
            if rag_product_values:
                metadata_filters = [MetadataFilter(
                    key="product",
                    value=",".join(rag_product_values),  # comma-separated for IN operator
                    operator="IN"
                )]
            
            # 스트리밍 생성
            client = _get_file_search_client()
            
            full_response = ""
            async for chunk in client.stream_search(
                query=query,
                store_names=rag_stores,
                metadata_filters=metadata_filters if metadata_filters else None,
                conversation_history=history[-4:],  # 최근 4턴
                system_instruction=system_prompt,
            ):
                # stream_search returns {"event": "result", "data": {"text": "..."}}
                if chunk.get("event") == "result" and chunk.get("data", {}).get("text"):
                    text = chunk["data"]["text"]
                    full_response = text  # 전체 응답
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
# 퀴즈 문제 조회 (자가 점검용)
# ============================================

async def _generate_quiz_questions(module_id: UUID, module_name: str, module_desc: str = "") -> List[QuizQuestion]:
    """Gemini를 사용하여 퀴즈 문제 생성 및 DB 저장."""
    try:
        client = get_gemini_client()
        prompt = f"""
        Topic: {module_name}
        Description: {module_desc or module_name}
        
        Generate 3 multiple-choice quiz questions to check understanding of this topic.
        Target audience: New employees learning the system.
        Language: Korean.
        
        Format: JSON Array of objects.
        Each object must have:
        - question: string
        - choices: array of objects {{"id": "a", "text": "..."}} (ids should be a, b, c, d)
        - context: string (optional, brief background context)
        - correct_choice_id: string (id of the correct choice, e.g., "a")
        - explanation: string (explanation of why the answer is correct)
        - learning_point: string (key takeaway)
        
        Output ONLY the JSON array.
        """
        
        response_stream = client.generate_content_stream(contents=prompt)
        text = ""
        async for chunk in response_stream:
            if chunk.text:
                text += chunk.text
        
        # Clean up markdown code blocks if present
        if text.strip().startswith("```json"):
            text = text.strip()[7:]
        if text.strip().endswith("```"):
            text = text.strip()[:-3]
            
        data = json.loads(text)
        
        repo = get_curriculum_repository()
        db_questions = []
        result_questions = []
        
        for i, item in enumerate(data):
            q_id = str(uuid4())
            
            # DB 저장용 데이터
            db_q = {
                "id": q_id,
                "module_id": str(module_id),
                "question_order": i + 1,
                "difficulty": "basic",
                "question": item["question"],
                "context": item.get("context"),
                "choices": item["choices"],
                "correct_choice_id": item["correct_choice_id"],
                "explanation": item["explanation"],
                "learning_point": item.get("learning_point"),
                "is_active": True
            }
            db_questions.append(db_q)
            
            # 반환용 데이터 (정답 제외)
            q = QuizQuestion(
                id=UUID(q_id),
                moduleId=module_id,
                questionOrder=i+1,
                question=item["question"],
                context=item.get("context"),
                choices=[QuizChoice(id=c["id"], text=c["text"]) for c in item["choices"]],
                relatedDocUrl=None
            )
            result_questions.append(q)
            
        # DB에 저장 (비동기적으로 처리하거나 기다림)
        try:
            await repo.create_questions(db_questions)
            logger.info(f"Successfully saved {len(db_questions)} generated questions to DB.")
        except Exception as e:
            logger.error(f"Failed to save generated questions to DB: {e}")
            
        return result_questions
    except Exception as e:
        logger.error(f"Failed to generate quiz questions: {e}")
        return []


@router.get("/modules/{module_id}/questions", response_model=List[QuizQuestion])
async def get_questions(
    module_id: UUID = Path(..., description="모듈 ID"),
):
    """
    모듈별 자가 점검 퀴즈 문제 조회.
    
    - 정답은 포함되지 않음
    - 학습 이해도 확인용 (통과/불통과 없음)
    """
    repo = get_curriculum_repository()
    questions = []
    
    try:
        questions = await repo.get_questions(module_id=module_id)
    except Exception as e:
        logger.warning(f"Failed to get questions from DB (might be missing tables): {e}")
        # DB 에러 시에도 AI 생성 시도로 넘어감
    
    if not questions:
        # 퀴즈가 없으면 AI로 생성 및 저장
        logger.info(f"No questions found for module {module_id}. Generating with AI...")
        
        module_name = "Onboarding Knowledge"
        module_desc = ""
        
        try:
            module = await repo.get_module_by_id(module_id)
            if module:
                module_name = module.nameKo
                module_desc = module.description
        except Exception:
            logger.warning(f"Failed to get module info for {module_id}, using default topic.")
            
        questions = await _generate_quiz_questions(module_id, module_name, module_desc)
            
    return questions


# ============================================
# 퀴즈 제출 (자가 점검)
# ============================================

@router.post("/modules/{module_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    module_id: UUID = Path(..., description="모듈 ID"),
    request: QuizSubmitRequest = None,  # type: ignore
):
    """
    자가 점검 퀴즈 제출 및 채점.
    
    - 통과/불통과 없음, 점수만 참고용으로 제공
    - 틀린 문제에 대한 설명 제공
    """
    if not request:
        raise HTTPException(status_code=400, detail="Request body is required")
    
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
        in_progress = sum(1 for m in modules if m.status == "learning")
        
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
                quizScore=None,
                quizAttempts=0,
                learningTimeMinutes=0,
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


# ============================================
# 디버그: 퀴즈 시도 조회
# ============================================

@router.get("/debug/quiz-attempts")
async def debug_quiz_attempts(
    session_id: str = Query(None, alias="sessionId", description="세션 ID"),
    module_id: str = Query(None, alias="moduleId", description="모듈 ID"),
):
    """디버그: quiz_attempts 테이블 조회."""
    try:
        repo = get_curriculum_repository()
        query = repo.client.table("quiz_attempts").select("*")
        
        if session_id:
            query = query.eq("session_id", session_id)
        if module_id:
            query = query.eq("module_id", module_id)
        
        response = query.order("created_at", desc=True).limit(10).execute()
        return {"attempts": response.data, "count": len(response.data)}
    except Exception as e:
        logger.error(f"Debug quiz attempts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/module-progress-schema")
async def debug_module_progress_schema():
    """디버그: module_progress 테이블 스키마 조회."""
    try:
        repo = get_curriculum_repository()
        # Get first row to see columns
        response = repo.client.table("module_progress").select("*").limit(1).execute()
        if response.data:
            columns = list(response.data[0].keys())
        else:
            columns = ["No data in table"]
        return {"columns": columns, "sample_data": response.data}
    except Exception as e:
        logger.error(f"Debug module progress schema error: {e}")
        raise HTTPException(status_code=500, detail=str(e))