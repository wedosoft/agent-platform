"""온보딩 전용 API 라우터."""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.gemini_client import get_gemini_client
from app.services.gemini_file_search import upload_document_to_store, get_store_documents
from app.services.onboarding_repository import get_onboarding_repository
from app.services.supabase_kb_client import get_kb_client
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

당신의 특징:
- 간결하고 본론 중심의 답변 (인사말이나 이름 언급 없이 바로 핵심으로)
- 실질적이고 실행 가능한 조언
- 생산성, 시간 관리, 커뮤니케이션, 문제 해결, 협업에 대한 전문 지식
- 한국어로 답변

질문에 대해 바로 본론으로 들어가서 실용적인 조언을 제공하세요. 이름을 부르거나 인사말을 하지 마세요."""


def get_feedback_prompt(
    user_name: str,
    scenario_title: str,
    scenario_description: str,
    all_choices: List[str],
    selected_choice: str
) -> str:
    """시나리오 피드백 생성을 위한 프롬프트."""
    all_choices_text = '\n'.join(f'- {choice}' for choice in all_choices)
    
    return f"""당신은 글로벌 최상위 테크 기업의 노련한 시니어 매니저입니다.

업무 시나리오:
**제목:** {scenario_title}
**상황:** {scenario_description}

선택 가능한 행동들:
{all_choices_text}

**선택한 행동:** "{selected_choice}"

이 선택에 대해 명확하고 실행 가능한 피드백을 제공해 주세요.
**중요: 이름을 부르거나 인사말 없이 바로 본론으로 들어가세요.**
**피드백은 반드시 아래의 마크다운 서식을 정확히 따라야 합니다.**

### 🤷 선택에 대한 분석
(선택을 인정하고, 실제 업무 환경에서 가질 수 있는 장점과 단점을 균형 있게 분석)

---

### 💡 추천하는 접근 방식
(이 시나리오에 적용할 수 있는 가장 효과적인 업무 원칙이나 사고 모델 설명. 가장 이상적인 행동과 그 이유를 명확히 제시)

---

### 🤔 다른 선택지들에 대한 고찰
(선택되지 않은 다른 옵션들이 왜 덜 효과적인지 간략하게 설명)

---

### ⭐ 핵심 정리
> (앞으로 유사한 상황에서 기억하고 적용할 수 있는 핵심 원칙이나 교훈을 blockquote 형식으로 작성)

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
    return f"""당신은 글로벌 최상위 테크 기업의 시니어 멘토입니다.

**상황:**
- **시나리오:** {scenario_title} ({scenario_description})
- **이전 조언 요약:** {original_feedback[:500]}...

**추가 질문:** "{question}"

이 질문에 대해 명확하고, 실질적이며, 실행 가능한 답변을 해주세요.
**중요: 이름을 부르거나 인사말 없이 바로 본론으로 들어가세요.**
답변은 마크다운 형식으로, 한국어로 해주세요."""


# ============================================
# SSE 헬퍼
# ============================================

def format_sse(event: str, data: dict) -> str:
    """SSE 포맷으로 변환."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================
# 세션 관리 (Supabase 영속화, 폴백: 인메모리)
# ============================================

# 대화 히스토리용 인메모리 캐시 (세션 메타데이터는 Supabase에 저장)
_conversation_cache: dict = {}


@router.post("/session", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """온보딩 세션 생성."""
    import uuid
    session_id = f"onboarding-{uuid.uuid4().hex[:8]}"

    # Supabase에 세션 저장 (또는 인메모리 폴백)
    repo = get_onboarding_repository()
    await repo.create_session(session_id, request.userName)

    # 대화 히스토리 캐시 초기화
    _conversation_cache[session_id] = {
        "userName": request.userName,
        "conversationHistory": [],
    }

    logger.info(f"Created onboarding session: {session_id} for user: {request.userName}")

    return CreateSessionResponse(
        sessionId=session_id,
        message="온보딩 세션이 시작되었습니다."
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

    # 대화 히스토리 캐시에서 조회, 없으면 Supabase에서 세션 정보 조회
    session = _conversation_cache.get(sessionId)
    if not session:
        repo = get_onboarding_repository()
        db_session = await repo.get_session(sessionId)
        user_name = db_session.user_name if db_session else "신입사원"
        session = {"userName": user_name, "conversationHistory": []}
        _conversation_cache[sessionId] = session

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
                {"role": "model", "parts": [{"text": "네, 무엇이든 물어보세요."}]},
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
# 진행도 관리 (Supabase 영속화)
# ============================================

@router.post("/progress")
async def save_progress(request: SaveProgressRequest):
    """시나리오 완료 진행도 저장 (Supabase에 영속화)."""
    repo = get_onboarding_repository()

    try:
        await repo.save_progress(
            session_id=request.sessionId,
            scenario_id=request.scenarioId,
            choice_id=request.choiceId,
            feedback_rating=request.feedbackRating,
        )
        logger.info(f"Saved progress for session {request.sessionId}: scenario {request.scenarioId}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress/{sessionId}")
async def get_progress(sessionId: str):
    """진행도 조회 (Supabase에서 조회)."""
    repo = get_onboarding_repository()

    try:
        summary = await repo.get_progress_summary(sessionId, total_scenarios=12)
        return {
            "userId": summary.user_id,
            "userName": summary.user_name,
            "completedScenarios": [
                {
                    "scenarioId": p.scenario_id,
                    "choiceId": p.choice_id,
                    "feedbackRating": p.feedback_rating,
                    "completedAt": p.completed_at.isoformat() if p.completed_at else None,
                }
                for p in summary.completed_scenarios
            ],
            "totalScenarios": summary.total_scenarios,
            "completionRate": summary.completion_rate,
        }
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress")
async def get_all_progress():
    """모든 세션의 진행도 요약 조회 (관리자용)."""
    repo = get_onboarding_repository()

    try:
        summaries = await repo.get_all_sessions_summary()
        return {"sessions": summaries}
    except Exception as e:
        logger.error(f"Failed to get all progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ============================================
# 지식 베이스 (Knowledge Base)
# ============================================

class StructureKnowledgeRequest(BaseModel):
    """지식 구조화 요청."""
    rawContent: str
    category: str


class CreateKnowledgeArticleRequest(BaseModel):
    """지식 아티클 생성 요청."""
    title: str
    author: str
    category: str
    rawContent: str
    structuredSummary: str


class KnowledgeArticleResponse(BaseModel):
    """지식 아티클 응답."""
    id: str
    title: str
    author: str
    category: str
    rawContent: str
    structuredSummary: Optional[str] = None
    createdAt: str


# 인메모리 저장소 (실제 프로덕션에서는 Supabase 사용)
_knowledge_store: list = []


def get_structure_prompt(category: str) -> str:
    """범주별 구조화 프롬프트 생성."""
    category_prompts = {
        "handover": """
다음 인수인계 내용을 구조화하세요:
1. **핵심 진행 사항**: 현재 진행 중인 프로젝트/업무
2. **주요 연락처**: 연락해야 할 사람과 이유
3. **파일/접근 정보**: 파일 위치, 계정 정보 등
4. **주의사항/정책**: 반드시 지켜야 할 사항
5. **액션 아이템**: 즉시 해야 할 일
""",
        "process": """
다음 업무 프로세스를 구조화하세요:
1. **개요**: 업무 목적과 배경
2. **단계별 절차**: 순서대로 정리
3. **주의사항**: 실수하기 쉬운 부분
4. **관련 시스템/도구**: 사용하는 도구
5. **담당자/문의처**: 도움 받을 수 있는 곳
""",
        "tips": """
다음 팁/노하우를 구조화하세요:
1. **핵심 포인트**: 가장 중요한 내용
2. **적용 방법**: 실제 적용하는 방법
3. **주의점**: 잘못 적용하면 안되는 경우
4. **관련 팁**: 함께 알면 좋은 내용
""",
        "company": """
다음 회사 생활 정보를 구조화하세요:
1. **요약**: 핵심 내용
2. **상세 정보**: 알아야 할 세부사항
3. **유용한 팁**: 활용하면 좋은 점
4. **관련 정보**: 함께 알면 좋은 내용
""",
        "tools": """
다음 시스템/도구 정보를 구조화하세요:
1. **개요**: 도구의 용도
2. **접근 방법**: 어떻게 접근하는지
3. **주요 기능**: 자주 사용하는 기능
4. **팁**: 효율적으로 사용하는 방법
5. **문제 해결**: 자주 발생하는 문제와 해결법
""",
    }
    return category_prompts.get(category, """
다음 내용을 구조화하세요:
1. **핵심 내용**: 가장 중요한 포인트
2. **상세 정보**: 세부 사항
3. **관련 정보**: 참고할 내용
""")


@router.post("/knowledge/structure")
async def structure_knowledge_content(request: StructureKnowledgeRequest):
    """AI를 사용하여 지식 콘텐츠 구조화."""
    try:
        client = get_gemini_client()

        structure_guide = get_structure_prompt(request.category)
        prompt = f"""당신은 사내 지식을 정리하는 전문가입니다.

{structure_guide}

원본 내용:
"{request.rawContent}"

위 내용을 마크다운 형식으로 구조화하세요. 한국어로 작성하세요."""

        response = await client.generate_content(
            contents=prompt,
            config={"thinking_config": {"thinking_budget": 0}}
        )

        return {"structuredSummary": response.text}

    except Exception as e:
        logger.error(f"Knowledge structure failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge", response_model=List[KnowledgeArticleResponse])
async def get_knowledge_articles(category: Optional[str] = None):
    """지식 아티클 목록 조회."""
    articles = _knowledge_store

    if category:
        articles = [a for a in articles if a.get("category") == category]

    # 최신순 정렬
    articles = sorted(articles, key=lambda x: x.get("createdAt", ""), reverse=True)

    return articles


@router.post("/knowledge", response_model=KnowledgeArticleResponse)
async def create_knowledge_article(request: CreateKnowledgeArticleRequest):
    """지식 아티클 생성."""
    import uuid
    from datetime import datetime

    article = {
        "id": str(uuid.uuid4()),
        "title": request.title,
        "author": request.author,
        "category": request.category,
        "rawContent": request.rawContent,
        "structuredSummary": request.structuredSummary,
        "createdAt": datetime.now().strftime("%Y-%m-%d"),
    }

    _knowledge_store.append(article)
    logger.info(f"Created knowledge article: {article['title']}")

    return article


@router.delete("/knowledge/{article_id}")
async def delete_knowledge_article(article_id: str):
    """지식 아티클 삭제."""
    global _knowledge_store

    original_count = len(_knowledge_store)
    _knowledge_store = [a for a in _knowledge_store if a.get("id") != article_id]

    if len(_knowledge_store) == original_count:
        raise HTTPException(status_code=404, detail="Article not found")

    logger.info(f"Deleted knowledge article: {article_id}")
    return {"success": True}


# ============================================
# 학습 평가 (Assessment)
# ============================================

class AssessmentSubmitRequest(BaseModel):
    """퀴즈 답안 제출 요청."""
    sessionId: str
    trackId: str
    levelId: Optional[str] = None
    answers: List[dict]  # [{"questionId": str, "choiceId": str}]


# 트랙 정의 (정적 데이터)
ASSESSMENT_TRACKS = [
    {
        "id": "work_sense",
        "name": "업무 센스 체크",
        "description": "고객 응대, 업무 우선순위, 팀 협업 등 기본적인 업무 역량을 평가합니다.",
        "icon": "fas fa-lightbulb",
        "type": "work_sense",
    },
    {
        "id": "product_knowledge",
        "name": "제품 지식",
        "description": "시장 포지셔닝부터 세부 기능까지, 제품에 대한 체계적인 학습과 평가를 진행합니다.",
        "icon": "fas fa-graduation-cap",
        "type": "product_knowledge",
        "totalLevels": 4,
    },
]

# 레벨 정의 (제품 지식용)
ASSESSMENT_LEVELS = [
    {
        "id": "level_1",
        "trackId": "product_knowledge",
        "order": 1,
        "name": "시장과 포지셔닝",
        "description": "우리 제품이 속한 시장과 경쟁 환경을 이해합니다.",
        "passingScore": 80,
    },
    {
        "id": "level_2",
        "trackId": "product_knowledge",
        "order": 2,
        "name": "설계 철학과 목적",
        "description": "제품이 해결하는 핵심 문제와 설계 원칙을 학습합니다.",
        "passingScore": 80,
    },
    {
        "id": "level_3",
        "trackId": "product_knowledge",
        "order": 3,
        "name": "핵심 기능군 이해",
        "description": "주요 기능군의 필요성과 작동 방식을 파악합니다.",
        "passingScore": 80,
    },
    {
        "id": "level_4",
        "trackId": "product_knowledge",
        "order": 4,
        "name": "세부 기능 심화",
        "description": "각 기능의 상세 옵션과 고급 사용법을 학습합니다.",
        "passingScore": 80,
    },
]

# 샘플 문제 (업무 센스 체크)
WORK_SENSE_QUESTIONS = [
    {
        "id": "ws_q1",
        "trackId": "work_sense",
        "type": "scenario",
        "context": "고객이 급하게 기능 수정을 요청했습니다. 하지만 현재 다른 중요한 프로젝트 마감이 코앞입니다.",
        "question": "이 상황에서 가장 적절한 대응은?",
        "choices": [
            {"id": "a", "text": "고객 요청을 우선 처리하고 프로젝트 마감을 미룬다"},
            {"id": "b", "text": "프로젝트 마감을 우선하고 고객에게 기다려달라고 한다"},
            {"id": "c", "text": "상사에게 상황을 보고하고 우선순위 조정을 요청한다"},
            {"id": "d", "text": "두 가지 모두 야근해서 처리한다"},
        ],
        "correctChoiceId": "c",
        "explanation": "우선순위 충돌 상황에서는 독단적으로 결정하기보다 상사에게 상황을 공유하고 조직 차원의 우선순위 판단을 받는 것이 바람직합니다.",
    },
    {
        "id": "ws_q2",
        "trackId": "work_sense",
        "type": "scenario",
        "context": "팀 회의 중 동료가 제시한 아이디어에 명백한 문제점이 보입니다.",
        "question": "가장 적절한 대응 방법은?",
        "choices": [
            {"id": "a", "text": "회의 중 즉시 문제점을 지적한다"},
            {"id": "b", "text": "회의 후 개인적으로 동료에게 이야기한다"},
            {"id": "c", "text": "문제점과 함께 개선 방안을 건설적으로 제안한다"},
            {"id": "d", "text": "다른 사람이 지적할 때까지 기다린다"},
        ],
        "correctChoiceId": "c",
        "explanation": "문제점만 지적하기보다 개선 방안과 함께 건설적으로 의견을 나누는 것이 팀 협업에 도움이 됩니다.",
    },
    {
        "id": "ws_q3",
        "trackId": "work_sense",
        "type": "scenario",
        "context": "처음 접하는 업무를 배정받았는데, 담당자가 휴가 중입니다.",
        "question": "어떻게 대응하시겠습니까?",
        "choices": [
            {"id": "a", "text": "담당자가 돌아올 때까지 기다린다"},
            {"id": "b", "text": "관련 문서를 찾아보고 시도해본 후, 막히는 부분을 정리한다"},
            {"id": "c", "text": "다른 팀원에게 전체 업무를 대신 해달라고 요청한다"},
            {"id": "d", "text": "상사에게 업무를 못하겠다고 보고한다"},
        ],
        "correctChoiceId": "b",
        "explanation": "먼저 스스로 조사하고 시도해본 후 구체적인 질문을 정리하면 효율적으로 도움을 받을 수 있습니다.",
    },
]

# 진행도 저장 (인메모리)
_assessment_progress: dict = {}

# 학습 콘텐츠 프롬프트 (레벨별)
LEARNING_CONTENT_PROMPTS = {
    "level_1": """다음 주제에 대해 학습 콘텐츠를 생성해주세요:

## 시장과 포지셔닝

1. **시장 이해**: 우리 제품이 속한 시장의 현황과 트렌드
2. **경쟁 환경**: 주요 경쟁사와 우리 제품의 차별점
3. **타겟 고객**: 우리 제품의 주요 고객군과 그들의 니즈
4. **가치 제안**: 우리 제품이 제공하는 핵심 가치

제품 문서를 참고하여 구체적이고 실용적인 내용으로 작성해주세요.
마크다운 형식으로, 한국어로 답변해주세요.""",

    "level_2": """다음 주제에 대해 학습 콘텐츠를 생성해주세요:

## 설계 철학과 목적

1. **핵심 문제**: 우리 제품이 해결하고자 하는 핵심 문제
2. **설계 원칙**: 제품을 설계할 때 적용된 주요 원칙들
3. **아키텍처 개요**: 사용자 관점에서 제품의 구조
4. **주요 시나리오**: 제품의 대표적인 사용 사례

제품 문서를 참고하여 '왜' 이렇게 설계되었는지 중심으로 작성해주세요.
마크다운 형식으로, 한국어로 답변해주세요.""",

    "level_3": """다음 주제에 대해 학습 콘텐츠를 생성해주세요:

## 핵심 기능군 이해

각 주요 기능군에 대해:
1. **왜 필요한가?**: 이 기능이 존재하는 이유
2. **무엇인가?**: 기능의 개요와 핵심 개념
3. **어떻게 작동하나?**: 기본적인 사용 방법
4. **다른 기능과의 연결**: 기능 간 관계

제품 문서를 참고하여 실제 업무에서 활용할 수 있는 관점으로 작성해주세요.
마크다운 형식으로, 한국어로 답변해주세요.""",

    "level_4": """다음 주제에 대해 학습 콘텐츠를 생성해주세요:

## 세부 기능 심화

1. **상세 옵션**: 각 기능의 세부 설정과 옵션들
2. **고급 사용법**: 파워 유저를 위한 활용 팁
3. **트러블슈팅**: 자주 발생하는 문제와 해결 방법
4. **실전 활용 팁**: 효율적으로 사용하는 노하우

제품 문서를 참고하여 실무에서 바로 적용할 수 있는 내용으로 작성해주세요.
마크다운 형식으로, 한국어로 답변해주세요.""",
}


@router.get("/assessment/tracks")
async def get_assessment_tracks():
    """학습 평가 트랙 목록 조회."""
    return ASSESSMENT_TRACKS


@router.get("/assessment/tracks/{track_id}/levels")
async def get_assessment_levels(
    track_id: str,
    sessionId: str = Query(...),
):
    """트랙의 레벨 목록 조회 (진행도 포함)."""
    levels = [l for l in ASSESSMENT_LEVELS if l["trackId"] == track_id]

    # 진행도 조회
    session_progress = _assessment_progress.get(sessionId, {})
    track_progress = session_progress.get(track_id, {})

    result = []
    for level in levels:
        level_progress = track_progress.get(level["id"], {})
        is_completed = level_progress.get("isPassed", False)
        score = level_progress.get("score", 0)

        # 첫 번째 레벨은 항상 언락, 이후는 이전 레벨 완료 시 언락
        is_unlocked = level["order"] == 1
        if level["order"] > 1:
            prev_level_id = f"level_{level['order'] - 1}"
            prev_progress = track_progress.get(prev_level_id, {})
            is_unlocked = prev_progress.get("isPassed", False)

        result.append({
            **level,
            "isUnlocked": is_unlocked,
            "isCompleted": is_completed,
            "score": score,
        })

    return result


@router.get("/assessment/learn/{track_id}/{level_id}/stream")
async def stream_learning_content(
    track_id: str,
    level_id: str,
):
    """학습 콘텐츠 스트리밍 (RAG 기반)."""

    prompt = LEARNING_CONTENT_PROMPTS.get(level_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Level not found")

    async def event_generator():
        try:
            client = get_gemini_client()

            # RAG 스토어 설정
            from google.genai import types

            rag_stores = []
            if STORE_PRODUCT:
                rag_stores.append(STORE_PRODUCT)

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
            model_name = client.models[0]

            response = client.client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )

            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield format_sse("chunk", {"text": chunk.text})

            yield format_sse("result", {"text": full_response})

        except Exception as e:
            logger.error(f"Learning content stream error: {e}")
            yield format_sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/assessment/mentor/chat/stream")
async def stream_mentor_chat(
    sessionId: str = Query(...),
    trackId: str = Query(...),
    levelId: str = Query(...),
    message: str = Query(...),
):
    """AI 멘토 채팅 스트리밍 (레벨 컨텍스트 포함)."""

    # 레벨 정보 조회
    level_info = next((l for l in ASSESSMENT_LEVELS if l["id"] == levelId), None)
    level_name = level_info["name"] if level_info else "학습"
    level_desc = level_info["description"] if level_info else ""

    system_prompt = f"""당신은 온보딩 학습 멘토입니다.
현재 학습자는 '{level_name}' 레벨을 학습 중입니다.
레벨 설명: {level_desc}

제품 문서를 참고하여 학습자의 질문에 친절하고 구체적으로 답변해주세요.
답변은 한국어로, 마크다운 형식으로 작성해주세요.
인사말이나 이름 언급 없이 바로 본론으로 들어가세요."""

    async def event_generator():
        try:
            client = get_gemini_client()

            # RAG 스토어 설정
            from google.genai import types

            rag_stores = []
            if STORE_PRODUCT:
                rag_stores.append(STORE_PRODUCT)

            tools = None
            if rag_stores:
                tools = [
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=rag_stores
                        )
                    )
                ]

            messages = [
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "네, 질문해주세요."}]},
                {"role": "user", "parts": [{"text": message}]},
            ]

            generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                tools=tools,
            )

            full_response = ""
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

            yield format_sse("result", {"text": full_response})

        except Exception as e:
            logger.error(f"Mentor chat stream error: {e}")
            yield format_sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/assessment/questions/{track_id}")
async def get_assessment_questions(
    track_id: str,
    levelId: Optional[str] = None,
):
    """퀴즈 문제 조회."""
    if track_id == "work_sense":
        questions = WORK_SENSE_QUESTIONS
    else:
        # 제품 지식 문제는 AI로 동적 생성 (추후 구현)
        # 현재는 샘플 반환
        questions = []

    # 정답 정보 제외하고 반환
    return [
        {
            "id": q["id"],
            "trackId": q["trackId"],
            "type": q["type"],
            "context": q.get("context"),
            "question": q["question"],
            "choices": q["choices"],
        }
        for q in questions
    ]


@router.post("/assessment/submit")
async def submit_assessment(request: AssessmentSubmitRequest):
    """퀴즈 답안 제출 및 채점."""

    # 문제 조회
    if request.trackId == "work_sense":
        questions = {q["id"]: q for q in WORK_SENSE_QUESTIONS}
    else:
        questions = {}

    # 채점
    correct_count = 0
    results = []

    for answer in request.answers:
        question = questions.get(answer["questionId"])
        if question:
            is_correct = answer["choiceId"] == question["correctChoiceId"]
            if is_correct:
                correct_count += 1

            results.append({
                "questionId": answer["questionId"],
                "choiceId": answer["choiceId"],
                "isCorrect": is_correct,
                "correctChoiceId": question["correctChoiceId"],
                "explanation": question["explanation"],
            })

    total = len(request.answers)
    score = int((correct_count / total) * 100) if total > 0 else 0
    is_passed = score >= 80

    # 진행도 저장
    if request.sessionId not in _assessment_progress:
        _assessment_progress[request.sessionId] = {}
    if request.trackId not in _assessment_progress[request.sessionId]:
        _assessment_progress[request.sessionId][request.trackId] = {}

    level_key = request.levelId or "default"
    _assessment_progress[request.sessionId][request.trackId][level_key] = {
        "score": score,
        "isPassed": is_passed,
        "completedAt": __import__("datetime").datetime.now().isoformat(),
    }

    logger.info(f"Assessment submitted: session={request.sessionId}, track={request.trackId}, score={score}")

    return {
        "trackId": request.trackId,
        "levelId": request.levelId,
        "score": score,
        "totalQuestions": total,
        "correctCount": correct_count,
        "isPassed": is_passed,
        "answers": results,
    }


@router.get("/assessment/progress/{session_id}")
async def get_assessment_progress(session_id: str):
    """진행도 조회."""
    progress = _assessment_progress.get(session_id, {})

    tracks = []
    for track_id, levels in progress.items():
        for level_id, data in levels.items():
            tracks.append({
                "trackId": track_id,
                "levelId": level_id if level_id != "default" else None,
                "score": data.get("score", 0),
                "isPassed": data.get("isPassed", False),
                "completedAt": data.get("completedAt"),
            })

    return {"tracks": tracks}


# ============================================
# 제품별 지식 학습 (Product Knowledge)
# ============================================

# 지원 제품 목록
PRODUCTS = [
    {
        "id": "freshservice",
        "name": "Freshservice",
        "name_ko": "프레시서비스",
        "description": "IT Service Management",
        "description_ko": "IT 서비스 관리",
        "icon": "cog",
        "color": "blue",
    },
    {
        "id": "freshdesk",
        "name": "Freshdesk",
        "name_ko": "프레시데스크",
        "description": "Customer Support (Omni 포함)",
        "description_ko": "고객 지원 (Omni 포함)",
        "icon": "headset",
        "color": "green",
    },
    {
        "id": "freshsales",
        "name": "Freshsales",
        "name_ko": "프레시세일즈",
        "description": "CRM & Sales",
        "description_ko": "CRM 및 영업",
        "icon": "chart-line",
        "color": "purple",
    },
    {
        "id": "freshchat",
        "name": "Freshchat",
        "name_ko": "프레시챗",
        "description": "Messaging & Chat",
        "description_ko": "메시징 및 채팅",
        "icon": "comments",
        "color": "orange",
    },
]


@router.get("/products")
async def get_products():
    """지원 제품 목록 조회."""
    return PRODUCTS


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """단일 제품 정보 조회."""
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}/categories")
async def get_product_categories(product_id: str):
    """제품별 카테고리 목록 조회 (Supabase kb_categories)."""
    try:
        kb_client = get_kb_client()
        categories = kb_client.get_categories(product_id)

        # 프론트엔드 친화적 형식으로 변환
        return [
            {
                "id": cat["id"],
                "name": cat.get("name_ko") or cat["name_en"],
                "nameEn": cat["name_en"],
                "nameKo": cat.get("name_ko"),
                "slug": cat["slug"],
                "description": cat.get("description_ko") or cat.get("description_en"),
                "displayOrder": cat["display_order"],
            }
            for cat in categories
        ]
    except Exception as e:
        logger.error(f"Failed to get categories for {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/categories/{category_slug}")
async def get_product_category(product_id: str, category_slug: str):
    """단일 카테고리 상세 조회."""
    try:
        kb_client = get_kb_client()
        category = kb_client.get_category_by_slug(product_id, category_slug)

        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        return {
            "id": category["id"],
            "name": category.get("name_ko") or category["name_en"],
            "nameEn": category["name_en"],
            "nameKo": category.get("name_ko"),
            "slug": category["slug"],
            "description": category.get("description_ko") or category.get("description_en"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get category {category_slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/categories/{category_slug}/folders")
async def get_category_folders(product_id: str, category_slug: str):
    """카테고리 내 폴더 목록 조회."""
    try:
        kb_client = get_kb_client()

        # 먼저 카테고리 ID 조회
        category = kb_client.get_category_by_slug(product_id, category_slug)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        folders = kb_client.get_folders_by_category(product_id, category["id"])

        return [
            {
                "id": folder["id"],
                "name": folder.get("name_ko") or folder["name_en"],
                "nameEn": folder["name_en"],
                "nameKo": folder.get("name_ko"),
                "slug": folder["slug"],
                "displayOrder": folder["display_order"],
            }
            for folder in folders
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get folders for {category_slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/categories/{category_slug}/documents")
async def get_category_documents(product_id: str, category_slug: str, limit: int = 50):
    """카테고리 내 문서 목록 조회."""
    try:
        kb_client = get_kb_client()

        # 먼저 카테고리 ID 조회
        category = kb_client.get_category_by_slug(product_id, category_slug)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        documents = kb_client.get_documents_by_category(product_id, category["id"], limit)

        return [
            {
                "id": doc["id"],
                "csvId": doc["csv_id"],
                "title": doc.get("title_ko") or doc["title_en"],
                "titleEn": doc["title_en"],
                "titleKo": doc.get("title_ko"),
                "slug": doc.get("short_slug") or doc["slug"],
                "folderId": doc.get("folder_id"),
            }
            for doc in documents
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get documents for {category_slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/stats")
async def get_product_stats(product_id: str):
    """제품별 문서 통계 조회."""
    try:
        kb_client = get_kb_client()
        stats = kb_client.get_product_stats(product_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats for {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 제품별 학습 콘텐츠 스트리밍
# ============================================

def format_documents_for_context(documents: List[dict], max_chars: int = 8000) -> str:
    """문서 목록을 AI 컨텍스트용 텍스트로 변환."""
    context_parts = []
    total_chars = 0

    for doc in documents:
        title = doc.get("title_ko") or doc.get("title_en", "")
        content = doc.get("content_text_ko") or doc.get("content_text_en", "")

        # 문서별 최대 길이 제한
        if len(content) > 2000:
            content = content[:2000] + "..."

        doc_text = f"### {title}\n{content}\n"

        if total_chars + len(doc_text) > max_chars:
            break

        context_parts.append(doc_text)
        total_chars += len(doc_text)

    return "\n".join(context_parts)


@router.get("/products/{product_id}/categories/{category_slug}/learn/stream")
async def stream_category_learning(
    product_id: str,
    category_slug: str,
):
    """카테고리별 학습 콘텐츠 스트리밍 (Supabase 문서 기반)."""
    try:
        kb_client = get_kb_client()

        # 카테고리 정보 조회
        category = kb_client.get_category_by_slug(product_id, category_slug)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        # 해당 카테고리의 문서 조회
        documents = kb_client.get_documents_by_category(product_id, category["id"], limit=10)

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found for this category")

        # 컨텍스트 생성
        context = format_documents_for_context(documents)
        category_name = category.get("name_ko") or category["name_en"]

        # 학습 콘텐츠 생성 프롬프트
        prompt = f"""당신은 IT 솔루션 교육 전문가입니다.
다음은 '{category_name}' 카테고리의 문서입니다.

---
{context}
---

위 문서를 바탕으로 신입사원을 위한 학습 콘텐츠를 작성하세요.

포함할 내용:
1. **개요**: 이 기능이 왜 필요한지, 비즈니스 가치
2. **핵심 개념**: 알아야 할 주요 용어와 개념
3. **주요 기능**: 핵심 기능들의 설명
4. **사용 방법**: 단계별 사용 가이드
5. **실무 팁**: 효과적으로 활용하는 방법
6. **자주 묻는 질문**: 예상되는 질문과 답변

마크다운 형식으로, 한국어로 작성하세요.
문서에 없는 내용은 추측하지 마세요."""

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to prepare learning content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    async def event_generator():
        try:
            client = get_gemini_client()

            from google.genai import types

            generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

            full_response = ""
            model_name = client.models[0]

            response = client.client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=generation_config,
            )

            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield format_sse("chunk", {"text": chunk.text})

            yield format_sse("result", {"text": full_response})

        except Exception as e:
            logger.error(f"Learning content stream error: {e}")
            yield format_sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================
# 제품별 AI 채팅 스트리밍
# ============================================

@router.get("/products/{product_id}/chat/stream")
async def stream_product_chat(
    product_id: str,
    message: str = Query(..., description="사용자 질문"),
    sessionId: Optional[str] = Query(None, description="세션 ID"),
    categorySlug: Optional[str] = Query(None, description="카테고리 슬러그 (선택)"),
):
    """제품별 AI 채팅 스트리밍 (Supabase 문서 기반).

    categorySlug이 제공되면 해당 카테고리 내 문서만 검색,
    없으면 제품 전체 문서에서 검색합니다.
    """
    try:
        kb_client = get_kb_client()
        product = next((p for p in PRODUCTS if p["id"] == product_id), None)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        product_name = product.get("name_ko") or product["name"]

        # 카테고리 필터링 (선택)
        category_context = ""
        if categorySlug:
            category = kb_client.get_category_by_slug(product_id, categorySlug)
            if category:
                documents = kb_client.get_documents_by_category(product_id, category["id"], limit=5)
                category_name = category.get("name_ko") or category["name_en"]
                category_context = f"\n현재 학습 중인 카테고리: {category_name}\n"
            else:
                documents = []
        else:
            # 텍스트 검색으로 관련 문서 찾기
            documents = kb_client.text_search(message, product_filter=product_id, limit=5)

        # 컨텍스트 생성
        context = format_documents_for_context(documents) if documents else "관련 문서를 찾지 못했습니다."

        # 시스템 프롬프트
        system_prompt = f"""당신은 {product_name} 제품 전문가입니다.{category_context}

다음 문서를 참고하여 질문에 답변하세요:

---
{context}
---

답변 규칙:
- 한국어로 답변
- 마크다운 형식 사용
- 구체적이고 실용적인 정보 제공
- 문서에 없는 내용은 "해당 정보는 문서에서 확인되지 않습니다"라고 답변
- 인사말 없이 바로 본론으로"""

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to prepare chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    async def event_generator():
        try:
            client = get_gemini_client()

            from google.genai import types

            messages = [
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "네, 무엇이든 질문해주세요."}]},
                {"role": "user", "parts": [{"text": message}]},
            ]

            generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

            full_response = ""
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

            yield format_sse("result", {"text": full_response})

        except Exception as e:
            logger.error(f"Product chat stream error: {e}")
            yield format_sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
