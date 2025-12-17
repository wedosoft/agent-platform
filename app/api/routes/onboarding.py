"""온보딩 전용 API 라우터."""

import json
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import Client, ClientOptions, create_client

from app.services.gemini_client import get_gemini_client
from app.services.onboarding_repository import get_onboarding_repository
from app.services.supabase_kb_client import get_kb_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])

settings = get_settings()

# 온보딩에서 사용할 RAG 스토어
STORE_PRODUCT = settings.gemini_store_common      # 제품 지식 (Freshworks, Google 등)


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

MENTOR_SYSTEM_PROMPT = """당신은 신입사원을 돕는 친절하고 전문적인 시니어 멘토 '온보딩 나침반'입니다.

당신의 특징:
- 친절하고 부드러운 '해요체' 사용 (예: ~해요, ~입니다)
- 신입사원의 입장을 이해하고 공감하는 태도
- 실질적이고 실행 가능한 조언을 알기 쉽게 설명
- 생산성, 시간 관리, 커뮤니케이션, 문제 해결, 협업에 대한 전문 지식
- 한국어로 답변

질문에 대해 친절하게 설명하고, 신입사원이 업무에 잘 적응할 수 있도록 격려와 구체적인 가이드를 함께 제공하세요."""


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
    """온보딩 세션 조회 또는 생성 (사용자명 기반)."""
    import uuid

    repo = get_onboarding_repository()

    # 1. 사용자 이름으로 기존 세션 찾기
    existing_session = await repo.get_session_by_user_name(request.userName)

    if existing_session:
        # 기존 세션 재사용
        session_id = existing_session.session_id
        logger.info(f"Reusing existing session: {session_id} for user: {request.userName}")

        # 대화 히스토리 캐시 확인 (없으면 초기화)
        if session_id not in _conversation_cache:
            _conversation_cache[session_id] = {
                "userName": request.userName,
                "conversationHistory": [],
            }

        return CreateSessionResponse(
            sessionId=session_id,
            message="기존 세션을 불러왔습니다."
        )

    # 2. 새 세션 생성
    session_id = f"onboarding-{uuid.uuid4().hex[:8]}"
    await repo.create_session(session_id, request.userName)

    # 대화 히스토리 캐시 초기화
    _conversation_cache[session_id] = {
        "userName": request.userName,
        "conversationHistory": [],
    }

    logger.info(f"Created new onboarding session: {session_id} for user: {request.userName}")

    return CreateSessionResponse(
        sessionId=session_id,
        message="새 온보딩 세션이 시작되었습니다."
    )



async def classify_intent(query: str) -> str:
    """사용자 질문의 의도를 분류합니다 (product vs general)."""
    try:
        client = get_gemini_client()
        prompt = f"""
        다음 질문이 '특정 제품(Freshworks, Google Workspace, Monday.com 등)의 기능이나 사용법'에 관한 것이면 'product',
        '회사 생활, 온보딩, 일반적인 업무 팁, 인사/복지' 등에 관한 것이면 'general'로 분류하세요.
        
        질문: "{query}"
        
        답변은 오직 'product' 또는 'general' 단어 하나만 출력하세요.
        """
        
        response = client.generate_content(
            contents=prompt,
            config={"thinking_config": {"thinking_budget": 0}}
        )
        
        intent = response.text.strip().lower()
        if "product" in intent:
            return "product"
        return "general"
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}")
        return "general"  # 기본값


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
    
    # 의도 분류 및 RAG 검색
    intent = await classify_intent(query)
    rag_context = ""
    
    if intent == "product":
        try:
            kb_client = get_kb_client()
            # 모든 제품에 대해 검색 (product_filter=None)
            documents = kb_client.text_search(query, limit=3)
            if documents:
                rag_context = format_documents_for_context(documents)
                rag_context = f"\n\n[참고 문서]\n{rag_context}\n\n위 참고 문서를 바탕으로 답변해주세요."
        except Exception as e:
            logger.error(f"Product RAG search failed: {e}")

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
            
            # 현재 질문 (RAG 컨텍스트 포함)
            final_query = query + rag_context
            messages.append({"role": "user", "parts": [{"text": final_query}]})
            
            # RAG 검색 설정 (여러 스토어 동시 검색)
            from google.genai import types

            # 스토어가 있으면 파일 검색 도구 추가
            tools = None
            # TODO: google-genai SDK 1.47.0에서 FileSearch 타입을 지원하지 않아 임시 비활성화
            # if rag_stores:
            #     tools = [
            #         types.Tool(
            #             file_search=types.FileSearch(
            #                 file_search_store_names=rag_stores
            #             )
            #         )
            #     ]

            generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                # tools=tools,
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
            
            # 히스토리에 추가 (저장은 원본 쿼리로)
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


class UpdateKnowledgeArticleRequest(BaseModel):
    """지식 아티클 수정 요청."""
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    rawContent: Optional[str] = None
    structuredSummary: Optional[str] = None


class KnowledgeArticleResponse(BaseModel):
    """지식 아티클 응답."""
    id: str
    title: str
    author: str
    category: str
    rawContent: str
    structuredSummary: Optional[str] = None
    createdAt: str


# 인메모리 저장소 제거 (Supabase 사용)
# _knowledge_store: list = []  # DEPRECATED: Supabase로 마이그레이션됨


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

        response = client.generate_content(
            contents=prompt,
            config={"thinking_config": {"thinking_budget": 0}}
        )

        return {"structuredSummary": response.text}

    except Exception as e:
        logger.error(f"Knowledge structure failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge", response_model=List[KnowledgeArticleResponse])
async def get_knowledge_articles(category: Optional[str] = None):
    """지식 아티클 목록 조회 (Supabase)."""
    repo = get_onboarding_repository()
    articles = await repo.get_knowledge_articles(category=category)

    return [
        KnowledgeArticleResponse(
            id=article.id,
            title=article.title,
            author=article.author,
            category=article.category,
            rawContent=article.raw_content,
            structuredSummary=article.structured_summary,
            createdAt=article.created_at.strftime("%Y-%m-%d") if article.created_at else "",
        )
        for article in articles
    ]


@router.post("/knowledge", response_model=KnowledgeArticleResponse)
async def create_knowledge_article(request: CreateKnowledgeArticleRequest):
    """지식 아티클 생성 (Supabase)."""
    try:
        repo = get_onboarding_repository()
    except Exception as e:
        logger.error(f"Supabase configuration missing for knowledge create: {e}")
        raise HTTPException(status_code=500, detail="Supabase 설정이 없어 저장할 수 없습니다. 환경변수를 설정하세요.")

    try:
        article = await repo.create_knowledge_article(
            title=request.title,
            author=request.author,
            category=request.category,
            raw_content=request.rawContent,
            structured_summary=request.structuredSummary,
        )

        logger.info(f"Created knowledge article: {article.title}")

        return KnowledgeArticleResponse(
            id=article.id,
            title=article.title,
            author=article.author,
            category=article.category,
            rawContent=article.raw_content,
            structuredSummary=article.structured_summary,
            createdAt=article.created_at.strftime("%Y-%m-%d") if article.created_at else "",
        )
    except Exception as e:
        logger.error(f"Failed to create knowledge article: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/knowledge/{article_id}", response_model=KnowledgeArticleResponse)
async def update_knowledge_article(article_id: str, request: UpdateKnowledgeArticleRequest):
    """지식 아티클 수정 (Supabase)."""
    try:
        repo = get_onboarding_repository()
    except Exception as e:
        logger.error(f"Supabase configuration missing for knowledge update: {e}")
        raise HTTPException(status_code=500, detail="Supabase 설정이 없어 저장할 수 없습니다. 환경변수를 설정하세요.")

    try:
        article = await repo.update_knowledge_article(
            article_id=article_id,
            title=request.title,
            author=request.author,
            category=request.category,
            raw_content=request.rawContent,
            structured_summary=request.structuredSummary,
        )

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        logger.info(f"Updated knowledge article: {article.title}")

        return KnowledgeArticleResponse(
            id=article.id,
            title=article.title,
            author=article.author,
            category=article.category,
            rawContent=article.raw_content,
            structuredSummary=article.structured_summary,
            createdAt=article.created_at.strftime("%Y-%m-%d") if article.created_at else "",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update knowledge article: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/knowledge/{article_id}")
async def delete_knowledge_article(article_id: str):
    """지식 아티클 삭제 (Supabase)."""
    try:
        repo = get_onboarding_repository()
    except Exception as e:
        logger.error(f"Supabase configuration missing for knowledge delete: {e}")
        raise HTTPException(status_code=500, detail="Supabase 설정이 없어 저장할 수 없습니다. 환경변수를 설정하세요.")

    try:
        success = await repo.delete_knowledge_article(article_id)

        if not success:
            raise HTTPException(status_code=404, detail="Article not found")

        logger.info(f"Deleted knowledge article: {article_id}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete knowledge article: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 제품별 지식 학습 (Product Knowledge)
# ============================================

# 폴백용 제품 목록 (DB 조회 실패 시)
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
    },
]


def _fallback_products_by_id() -> Dict[str, Dict[str, Any]]:
    return {p["id"]: p for p in PRODUCTS_FALLBACK}


def _is_postgrest_table_missing_error(exc: Exception) -> bool:
    # Supabase/PostgREST error code: PGRST205 = "Could not find the table ... in the schema cache"
    text = str(exc)
    return "PGRST205" in text or ("schema cache" in text and "Could not find the table" in text)


@lru_cache
def _get_supabase_client(schema: str) -> Client:
    settings_local = get_settings()
    if not settings_local.supabase_common_url or not settings_local.supabase_common_service_role_key:
        raise RuntimeError("Supabase 설정이 없습니다. SUPABASE_COMMON_* 환경변수를 확인하세요.")

    return create_client(
        settings_local.supabase_common_url,
        settings_local.supabase_common_service_role_key,
        options=ClientOptions(schema=schema),
    )


def _normalize_product_row(
    row: Dict[str, Any],
    *,
    product_type: str,
) -> Optional[Dict[str, Any]]:
    product_id = row.get("id")
    if not product_id:
        return None

    # NOTE: DB 스키마/마이그레이션에 따라 컬럼명이 달라질 수 있어 최대한 유연하게 매핑한다.
    name = row.get("name_en") or row.get("name") or row.get("nameEn") or product_id
    name_ko = row.get("name_ko") or row.get("nameKo") or name
    description = row.get("description_en") or row.get("description") or ""
    description_ko = row.get("description_ko") or ""
    icon = row.get("icon") or ("layer-group" if product_type == "bundle" else "cube")
    color = row.get("color") or row.get("color_primary") or ("teal" if product_type == "bundle" else "blue")
    display_order = row.get("display_order", 99)

    return {
        "id": product_id,
        "name": name,
        "name_ko": name_ko,
        "description": description,
        "description_ko": description_ko,
        "icon": icon,
        "color": color,
        "product_type": product_type,
        "display_order": display_order,
    }


def _sort_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(products, key=lambda x: (x.get("display_order", 99), x.get("id", "")))


def _fetch_products_from_tables(client: Client) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []

    modules_resp = (
        client.table("product_modules")
        .select("*")
        .eq("is_active", True)
        .order("display_order")
        .execute()
    )
    for row in modules_resp.data or []:
        normalized = _normalize_product_row(row, product_type="standalone")
        if normalized:
            products.append(normalized)

    bundles_resp = (
        client.table("product_bundles")
        .select("*")
        .eq("is_active", True)
        .order("display_order")
        .execute()
    )
    for row in bundles_resp.data or []:
        normalized = _normalize_product_row(row, product_type="bundle")
        if normalized:
            products.append(normalized)

    return _sort_products(products)


def _fetch_products_from_curriculum_modules(client: Client) -> List[Dict[str, Any]]:
    """product_modules/product_bundles가 없을 때 curriculum_modules에서 제품 목록을 유도한다."""
    resp = (
        client.table("curriculum_modules")
        .select("target_product_id, target_product_type")
        .eq("is_active", True)
        .execute()
    )

    fallback_by_id = _fallback_products_by_id()
    seen: Dict[str, str] = {}
    for row in resp.data or []:
        product_id = row.get("target_product_id")
        product_type_raw = row.get("target_product_type") or "module"
        if not product_id:
            continue
        seen[product_id] = "bundle" if product_type_raw == "bundle" else "standalone"

    if not seen:
        return []

    products: List[Dict[str, Any]] = []
    for product_id, product_type in seen.items():
        base = fallback_by_id.get(product_id, {})
        products.append({
            "id": product_id,
            "name": base.get("name") or product_id,
            "name_ko": base.get("name_ko") or base.get("name") or product_id,
            "description": base.get("description") or "",
            "description_ko": base.get("description_ko") or "",
            "icon": base.get("icon") or ("layer-group" if product_type == "bundle" else "cube"),
            "color": base.get("color") or ("teal" if product_type == "bundle" else "blue"),
            "product_type": product_type,
            "display_order": base.get("display_order", 99),
        })

    return _sort_products(products)


def _load_products_best_effort() -> List[Dict[str, Any]]:
    """가능한 한 DB 기반 제품 목록을 반환하고, 불가하면 안전한 폴백을 사용한다."""
    repo = get_onboarding_repository()
    onboarding_client = repo.supabase

    # 1) onboarding 스키마에서 product_* 테이블 조회
    try:
        products = _fetch_products_from_tables(onboarding_client)
        if products:
            return products
    except Exception as exc:
        if not _is_postgrest_table_missing_error(exc):
            logger.warning(f"Failed to load products from onboarding schema tables: {exc}")

    # 2) public 스키마에서 product_* 테이블 조회 (마이그레이션이 public에 적용된 경우 대비)
    try:
        public_client = _get_supabase_client("public")
        products = _fetch_products_from_tables(public_client)
        if products:
            return products
    except Exception as exc:
        if not _is_postgrest_table_missing_error(exc):
            logger.warning(f"Failed to load products from public schema tables: {exc}")

    # 3) 커리큘럼 모듈에서 제품 목록 유도
    try:
        products = _fetch_products_from_curriculum_modules(onboarding_client)
        if products:
            return products
    except Exception as exc:
        logger.warning(f"Failed to derive products from curriculum_modules: {exc}")

    return PRODUCTS_FALLBACK


@router.get("/products")
async def get_products():
    """지원 제품 목록 조회 (product_modules + product_bundles 통합)."""
    return _load_products_best_effort()


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """단일 제품 정보 조회."""
    products = _load_products_best_effort()
    product = next((p for p in products if p.get("id") == product_id), None)
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
                thinking_config=types.ThinkingConfig(thinking_budget=1024),
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
        product = next((p for p in _load_products_best_effort() if p.get("id") == product_id), None)

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
                thinking_config=types.ThinkingConfig(thinking_budget=1024),
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
