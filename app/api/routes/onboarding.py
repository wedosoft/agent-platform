"""온보딩 전용 API 라우터."""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.gemini_client import get_gemini_client
from app.services.gemini_file_search import upload_document_to_store, get_store_documents
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])

settings = get_settings()

# 온보딩에서 사용할 RAG 스토어들
STORE_PRODUCT = settings.gemini_store_common      # 제품 지식 (Freshworks, Google 등)
STORE_HANDOVER = settings.gemini_store_onboarding  # 인수인계/프로세스 문서


# ============================================
# Request/Response Models
# ============================================

class CreateSessionRequest(BaseModel):
    """세션 생성 요청."""
    userName: str


class CreateSessionResponse(BaseModel):
    """세션 생성 응답."""
    sessionId: str
    message: str


class SaveProgressRequest(BaseModel):
    """진행도 저장 요청."""
    sessionId: str
    scenarioId: str
    choiceId: str
    feedbackRating: Optional[int] = None


# ============================================
# 시스템 프롬프트
# ============================================

MENTOR_SYSTEM_PROMPT = """당신은 글로벌 최상위 테크 기업의 시니어 멘토 '온보딩 나침반'입니다.
신입사원의 성장을 돕는 것이 당신의 역할입니다.

당신의 특징:
- 따뜻하고 격려하는 톤
- 실질적이고 실행 가능한 조언
- 생산성, 시간 관리, 커뮤니케이션, 문제 해결, 협업에 대한 전문 지식
- 한국어로 답변

신입사원이 겪을 수 있는 어려움에 대해 실용적인 조언을 제공하세요."""


def get_feedback_prompt(
    user_name: str,
    scenario_title: str,
    scenario_description: str,
    all_choices: List[str],
    selected_choice: str
) -> str:
    """시나리오 피드백 생성을 위한 프롬프트."""
    all_choices_text = '\n'.join(f'- {choice}' for choice in all_choices)
    
    return f"""당신은 글로벌 최상위 테크 기업의 노련한 시니어 매니저입니다. 신입 주니어 사원 {user_name}님에게 멘토링을 제공하는 역할을 수행해 주세요.

신입사원에게 다음과 같은 업무 시나리오가 주어졌습니다:
**시나리오 제목:** {scenario_title}
**상세 설명:** {scenario_description}

선택 가능한 행동들은 다음과 같았습니다:
{all_choices_text}

**신입사원의 선택:** "{selected_choice}"

이 선택에 대해 명확하고 실행 가능한 피드백을 제공해 주세요. **피드백은 반드시 아래의 마크다운 서식을 정확히 따라야 합니다.**

### 🤷 당신의 선택에 대한 분석
({user_name}님의 선택을 먼저 인정하고, 해당 선택이 실제 업무 환경에서 가질 수 있는 장점과 단점을 균형 있게 분석)

---

### 💡 추천하는 접근 방식
(이 시나리오에 적용할 수 있는 가장 효과적인 업무 원칙이나 사고 모델 설명. 가장 이상적인 행동과 그 이유를 명확히 제시)

---

### 🤔 다른 선택지들에 대한 고찰
(선택되지 않은 다른 옵션들이 왜 덜 효과적인지 간략하게 설명)

---

### ⭐ 핵심 정리
> ({user_name}님이 앞으로 유사한 상황에서 기억하고 적용할 수 있는 핵심 원칙이나 교훈을 blockquote 형식으로 작성)

**피드백 작성이 끝나면, 반드시 다음 줄에 %%%QUESTIONS%%% 라는 구분자를 삽입해주세요.**

그 다음 줄부터, 이 주제에 대해 더 깊이 생각해볼 수 있는 3개의 연관 질문을 각각 한 줄씩 작성해주세요. 질문 앞에는 번호나 글머리 기호를 붙이지 마세요."""


def get_followup_prompt(
    user_name: str,
    scenario_title: str,
    scenario_description: str,
    original_feedback: str,
    question: str
) -> str:
    """후속 질문 답변 생성을 위한 프롬프트."""
    return f"""당신은 글로벌 최상위 테크 기업의 시니어 멘토 '온보딩 나침반'입니다.

**상황:**
- **시나리오:** {scenario_title} ({scenario_description})
- **이전 조언 요약:** {original_feedback[:500]}...

신입사원 {user_name}님이 다음과 같은 추가 질문을 했습니다:
**질문:** "{question}"

이 질문에 대해 명확하고, 실질적이며, 실행 가능한 답변을 해주세요.
답변은 마크다운 형식으로, 한국어로 해주세요."""


# ============================================
# SSE 헬퍼
# ============================================

def format_sse(event: str, data: dict) -> str:
    """SSE 포맷으로 변환."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================
# 세션 관리 (간단한 인메모리 저장)
# ============================================

# 실제 프로덕션에서는 Redis/Supabase 사용
_sessions: dict = {}


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """온보딩 세션 생성."""
    import uuid
    session_id = f"onboarding-{uuid.uuid4().hex[:8]}"
    
    _sessions[session_id] = {
        "userName": request.userName,
        "conversationHistory": [],
        "progress": [],
    }
    
    logger.info(f"Created onboarding session: {session_id} for user: {request.userName}")
    
    return CreateSessionResponse(
        sessionId=session_id,
        message=f"안녕하세요, {request.userName}님! 온보딩 세션이 시작되었습니다."
    )


# ============================================
# 채팅 스트리밍 (AI 멘토)
# ============================================

@router.get("/chat/stream")
async def chat_stream(
    sessionId: str = Query(...),
    query: str = Query(...),
):
    """AI 멘토 채팅 스트리밍 (RAG 검색 포함)."""
    
    session = _sessions.get(sessionId)
    if not session:
        # 세션이 없으면 임시 생성
        session = {"userName": "신입사원", "conversationHistory": []}
        _sessions[sessionId] = session
    
    user_name = session.get("userName", "신입사원")
    history = session.get("conversationHistory", [])
    
    # 사용할 RAG 스토어 목록
    rag_stores = []
    if STORE_PRODUCT:
        rag_stores.append(STORE_PRODUCT)
    if STORE_HANDOVER:
        rag_stores.append(STORE_HANDOVER)
    
    async def event_generator():
        try:
            client = get_gemini_client()
            
            # 시스템 프롬프트 + 대화 히스토리 구성
            messages = [
                {"role": "user", "parts": [{"text": MENTOR_SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{"text": f"네, {user_name}님의 AI 멘토로서 도움을 드리겠습니다."}]},
            ]
            
            # 히스토리 추가 (최근 4턴)
            for turn in history[-4:]:
                messages.append({"role": "user", "parts": [{"text": turn.get("user", "")}]})
                messages.append({"role": "model", "parts": [{"text": turn.get("model", "")}]})
            
            # 현재 질문
            messages.append({"role": "user", "parts": [{"text": query}]})
            
            # RAG 검색 설정 (여러 스토어 동시 검색)
            from google.genai import types

            # 스토어가 있으면 파일 검색 도구 추가
            tools = None
            if rag_stores:
                tools = [
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=rag_stores
                        )
                    )
                ]

            generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                tools=tools,
            )

            full_response = ""

            # 스트리밍 생성
            model_name = client.models[0]
            response = client.client.models.generate_content_stream(
                model=model_name,
                contents=messages,
                config=generation_config,
            )
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield format_sse("chunk", {"text": chunk.text})
            
            # 히스토리에 추가
            history.append({"user": query, "model": full_response})
            session["conversationHistory"] = history[-10:]  # 최근 10턴만 유지
            
            yield format_sse("result", {"text": full_response})
            
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================
# 시나리오 피드백 스트리밍
# ============================================

@router.get("/feedback/stream")
async def feedback_stream(
    sessionId: str = Query(...),
    scenarioId: str = Query(...),
    scenarioTitle: str = Query(...),
    scenarioDescription: str = Query(...),
    selectedChoice: str = Query(...),
    userName: str = Query(...),
    allChoices: List[str] = Query(...),
):
    """시나리오 선택에 대한 피드백 스트리밍."""
    
    async def event_generator():
        try:
            client = get_gemini_client()
            
            prompt = get_feedback_prompt(
                user_name=userName,
                scenario_title=scenarioTitle,
                scenario_description=scenarioDescription,
                all_choices=allChoices,
                selected_choice=selectedChoice,
            )
            
            full_response = ""
            feedback_text = ""
            questions_buffer = ""
            separator_found = False
            separator = "%%%QUESTIONS%%%"
            
            async for chunk in client.generate_content_stream(
                contents=prompt,
                config={"thinking_config": {"thinking_budget": 0}}
            ):
                if chunk.text:
                    chunk_text = chunk.text
                    full_response += chunk_text
                    
                    if separator_found:
                        questions_buffer += chunk_text
                    else:
                        if separator in chunk_text:
                            separator_found = True
                            parts = chunk_text.split(separator)
                            feedback_text += parts[0]
                            if len(parts) > 1:
                                questions_buffer += parts[1]
                            yield format_sse("feedback_chunk", {"text": parts[0]})
                        else:
                            feedback_text += chunk_text
                            yield format_sse("feedback_chunk", {"text": chunk_text})
            
            # 후속 질문 파싱
            questions = []
            if questions_buffer:
                questions = [q.strip() for q in questions_buffer.strip().split('\n') if q.strip()]
            
            yield format_sse("questions", {"questions": questions})
            yield format_sse("result", {"text": feedback_text, "questions": questions})
            
        except Exception as e:
            logger.error(f"Feedback stream error: {e}")
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================
# 후속 질문 답변 스트리밍
# ============================================

@router.get("/followup/stream")
async def followup_stream(
    sessionId: str = Query(...),
    scenarioId: str = Query(...),
    scenarioTitle: str = Query(...),
    scenarioDescription: str = Query(...),
    originalFeedback: str = Query(...),
    question: str = Query(...),
    userName: str = Query(...),
):
    """후속 질문에 대한 답변 스트리밍."""
    
    async def event_generator():
        try:
            client = get_gemini_client()
            
            prompt = get_followup_prompt(
                user_name=userName,
                scenario_title=scenarioTitle,
                scenario_description=scenarioDescription,
                original_feedback=originalFeedback,
                question=question,
            )
            
            full_response = ""
            
            async for chunk in client.generate_content_stream(
                contents=prompt,
                config={"thinking_config": {"thinking_budget": 0}}
            ):
                if chunk.text:
                    full_response += chunk.text
                    yield format_sse("chunk", {"text": chunk.text})
            
            yield format_sse("result", {"text": full_response})
            
        except Exception as e:
            logger.error(f"Follow-up stream error: {e}")
            yield format_sse("error", {"message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================
# 진행도 관리
# ============================================

@router.post("/progress")
async def save_progress(request: SaveProgressRequest):
    """시나리오 완료 진행도 저장."""
    from datetime import datetime
    
    session = _sessions.get(request.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    progress = session.get("progress", [])
    progress.append({
        "scenarioId": request.scenarioId,
        "choiceId": request.choiceId,
        "feedbackRating": request.feedbackRating,
        "completedAt": datetime.utcnow().isoformat(),
    })
    session["progress"] = progress
    
    logger.info(f"Saved progress for session {request.sessionId}: scenario {request.scenarioId}")
    
    return {"success": True}


@router.get("/progress/{sessionId}")
async def get_progress(sessionId: str):
    """진행도 조회."""
    session = _sessions.get(sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    progress = session.get("progress", [])
    
    return {
        "userId": sessionId,
        "userName": session.get("userName", ""),
        "completedScenarios": progress,
        "totalScenarios": 12,  # 하드코딩된 시나리오 수
        "completionRate": len(progress) / 12 * 100,
    }


# ============================================
# 문서 업로드 (인수인계/프로세스 문서)
# ============================================

@router.post("/documents")
async def upload_onboarding_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    """온보딩/인수인계 문서 업로드."""
    if not STORE_HANDOVER:
        raise HTTPException(
            status_code=500,
            detail="Onboarding store not configured"
        )
    
    try:
        parsed_metadata = []
        if metadata:
            parsed_metadata = json.loads(metadata)
        
        file_content = await file.read()
        result = await upload_document_to_store(
            store_name=STORE_HANDOVER,
            file_name=file.filename or "document.txt",
            file_content=file_content,
            metadata=parsed_metadata,
        )
        
        logger.info(f"Uploaded document: {result.get('displayName')}")
        return result
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_onboarding_documents(
    category: Optional[str] = None,
):
    """업로드된 온보딩 문서 목록 조회."""
    if not STORE_HANDOVER:
        raise HTTPException(
            status_code=500,
            detail="Onboarding store not configured"
        )
    
    try:
        result = await get_store_documents(STORE_HANDOVER)
        documents = result.get("documents", [])
        
        # 카테고리 필터링
        if category:
            documents = [
                doc for doc in documents
                if any(
                    m.get("key") == "category" and m.get("stringValue") == category
                    for m in (doc.get("customMetadata") or [])
                )
            ]
        
        return documents
        
    except Exception as e:
        logger.error(f"Document list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_name:path}")
async def delete_onboarding_document(document_name: str):
    """온보딩 문서 삭제."""
    from app.services.gemini_file_search import delete_document
    
    try:
        await delete_document(document_name)
        logger.info(f"Deleted document: {document_name}")
        return {"success": True, "deleted": document_name}
        
    except Exception as e:
        logger.error(f"Document delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
