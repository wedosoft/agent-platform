import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models.common_documents import CommonDocumentCursor, CommonDocumentsFetchResult
from app.services import common_documents as common_documents_module
from app.services import pipeline_client as pipeline_client_module
from app.services import session_repository as session_repository_module
from app.services.common_chat_handler import get_common_chat_handler
from app.services.ticket_chat_handler import get_ticket_chat_handler
from app.services.freshdesk_client import FreshdeskClient


# Configure anyio to use only asyncio backend
@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def stub_llm_calls(monkeypatch):
    """테스트에서 외부 LLM 네트워크 호출이 발생하지 않도록 기본 stub 처리."""

    from app.services.llm_adapter import LLMAdapter

    async def fake_analyze_ticket(_self, _ticket_context, response_tone: str = "formal"):
        return {
            "intent": "inquiry",
            "sentiment": "neutral",
            "summary": "요약",
            "summary_sections": [
                {"title": "핵심 이슈", "content": "요약"},
                {"title": "현재 상태", "content": "설명"},
            ],
            "key_entities": [],
            "field_proposals": [],
        }

    async def fake_propose_fields_only(_self, _ticket_context, response_tone: str = "formal"):
        return {"field_proposals": []}

    async def fake_propose_solution(_self, _ticket_context, _search_results, _analysis_result):
        return {
            "cause": "원인",
            "solution": "해결",
            "field_updates": {},
            "reasoning": "근거",
        }

    monkeypatch.setattr(LLMAdapter, "analyze_ticket", fake_analyze_ticket, raising=True)
    monkeypatch.setattr(LLMAdapter, "propose_fields_only", fake_propose_fields_only, raising=True)
    monkeypatch.setattr(LLMAdapter, "propose_solution", fake_propose_solution, raising=True)


class DummyPipelineClient:
    def __init__(self) -> None:
        self.sessions = {}
        self.sync_count = 0

    def create_session(self):
        session_id = f"session-{len(self.sessions) + 1}"
        payload = {
            "sessionId": session_id,
            "createdAt": "2025-01-01T00:00:00Z",
            "ttlMinutes": 30,
        }
        self.sessions[session_id] = {
            **payload,
            "updatedAt": "2025-01-01T00:00:00Z",
            "questionHistory": [],
        }
        return payload

    def get_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if not session:
            raise pipeline_client_module.PipelineClientError(404, "not found", {"error": "not found"})
        return session

    def chat(self, payload):
        session_id = payload["sessionId"]
        session = self.get_session(session_id)
        session["questionHistory"].append(payload["query"])
        session["updatedAt"] = "2025-01-01T00:00:10Z"
        return {
            "text": "stub response",
            "sessionId": session_id,
            "filters": [],
        }

    def get_status(self):
        return {
            "ready": True,
            "ragStoreName": "store-default",
            "availableSources": ["store-default", "store-common"],
        }

    def list_common_products(self):
        return {"products": ["제품A", "제품B"]}

    def trigger_sync(self, payload):
        self.sync_count += 1
        return {
            "syncedAt": "2025-01-01T00:00:00Z",
            "ticketCount": 10,
            "articleCount": 5,
            "commonDocumentCount": 2,
            "errors": [],
            "ragStoreName": payload.get("ragStoreName", "store-default"),
        }


class DummyCommonDocumentsService:
    def list_products(self):
        return ["제품A", "제품B"]

    def fetch_documents(self, **_kwargs):
        return CommonDocumentsFetchResult(
            records=[{"id": 123, "updated_at": "2025-01-01T00:00:00Z"}],
            cursor=CommonDocumentCursor(id=999, updated_at="2025-01-01T00:00:00Z"),
        )


@pytest.fixture(autouse=True)
def override_pipeline_client():
    dummy = DummyPipelineClient()
    app.dependency_overrides[pipeline_client_module.get_pipeline_client] = lambda: dummy
    yield dummy
    app.dependency_overrides.pop(pipeline_client_module.get_pipeline_client, None)


@pytest.fixture(autouse=True)
def override_common_documents_service():
    dummy = DummyCommonDocumentsService()
    app.dependency_overrides[common_documents_module.get_common_documents_service] = lambda: dummy
    yield dummy
    app.dependency_overrides.pop(common_documents_module.get_common_documents_service, None)


@pytest.fixture()
def test_client() -> TestClient:
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def override_session_repository():
    settings = get_settings()
    repo = session_repository_module.InMemorySessionRepository(settings.session_ttl_minutes * 60)
    app.dependency_overrides[session_repository_module.get_session_repository] = lambda: repo
    yield repo
    app.dependency_overrides.pop(session_repository_module.get_session_repository, None)


@pytest.fixture(autouse=True)
def disable_common_chat_handler():
    app.dependency_overrides[get_common_chat_handler] = lambda: None
    yield
    app.dependency_overrides.pop(get_common_chat_handler, None)


@pytest.fixture(autouse=True)
def disable_ticket_chat_handler():
    app.dependency_overrides[get_ticket_chat_handler] = lambda: None
    yield
    app.dependency_overrides.pop(get_ticket_chat_handler, None)


@pytest.fixture(autouse=True)
def stub_freshdesk_conversations(monkeypatch):
    """테스트에서 Freshdesk 네트워크 호출이 발생하지 않도록 기본 stub 처리."""

    async def _stub_get_all_conversations(_self, _ticket_id: int):
        return []

    monkeypatch.setattr(FreshdeskClient, "get_all_conversations", _stub_get_all_conversations, raising=True)


@pytest.fixture(autouse=True)
def stub_ticket_analysis_orchestrator(request, monkeypatch):
    """테스트에서 Ticket Analysis Orchestrator를 stub 처리.

    Note: test_orchestrator.py의 TestTicketAnalysisOrchestrator 클래스는
    자체 mock을 사용하므로 이 stub을 건너뜁니다.
    """
    # Skip this stub for orchestrator tests that need their own mocks
    if request.node.get_closest_marker("no_orchestrator_stub"):
        return
    if "TestTicketAnalysisOrchestrator" in request.node.nodeid:
        return

    from app.services.orchestrator.ticket_analysis_orchestrator import (
        TicketAnalysisOrchestrator,
        AnalysisResult,
    )

    async def fake_run_ticket_analysis(
        _self, normalized_input, options, tenant_id
    ):
        """Fake orchestrator that returns a valid stub response."""
        import uuid
        from datetime import datetime, timezone

        ticket_id = normalized_input.get("ticket_id", "unknown")
        has_description = bool(
            normalized_input.get("description") or normalized_input.get("description_text")
        )
        has_conversations = bool(normalized_input.get("conversations"))

        confidence = 0.5 if has_description else 0.2
        if has_conversations:
            confidence += 0.3

        if confidence >= 0.9:
            gate = "CONFIRM"
        elif confidence >= 0.7:
            gate = "EDIT"
        elif confidence >= 0.5:
            gate = "DECIDE"
        else:
            gate = "TEACH"

        return AnalysisResult(
            analysis_id=str(uuid.uuid4()),
            analysis={
                "narrative": {"summary": f"Stub analysis for ticket {ticket_id}", "timeline": []},
                "root_cause": None,
                "resolution": [],
                "confidence": confidence,
                "open_questions": [],
                "risk_tags": [],
                "intent": "inquiry",
                "sentiment": "neutral",
                "field_proposals": [],
                "evidence": [],
            },
            gate=gate,
            meta={
                "llm_provider": "stub",
                "llm_model": "stub-model",
                "prompt_version": "ticket_analysis_cot_v1",
                "latency_ms": 100,
                "token_usage": {"input": 0, "output": 0},
                "retrieval_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            success=True,
        )

    monkeypatch.setattr(
        TicketAnalysisOrchestrator,
        "run_ticket_analysis",
        fake_run_ticket_analysis,
        raising=True,
    )
