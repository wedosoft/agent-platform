from fastapi.testclient import TestClient

from app.main import app
from app.models.analyzer import AnalyzerClarification, AnalyzerResult
from app.models.metadata import MetadataFilter
from app.models.session import ChatResponse
from app.services.common_chat_handler import get_common_chat_handler
from app.services.query_filter_analyzer import get_query_filter_analyzer


def test_chat_flow(test_client: TestClient, override_pipeline_client):
    session_id = test_client.post("/api/session").json()["sessionId"]
    override_pipeline_client.sessions[session_id] = {
        "sessionId": session_id,
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "questionHistory": [],
    }
    payload = {
        "sessionId": session_id,
        "query": "테스트 질문",
        "sources": ["store-a"],
    }
    response = test_client.post("/api/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "stub response"

    detail = test_client.get(f"/api/session/{session_id}").json()
    assert detail["questionHistory"] == ["테스트 질문"]


def test_chat_uses_common_handler(test_client: TestClient):
    session_id = test_client.post("/api/session").json()["sessionId"]

    class StubHandler:
        def __init__(self) -> None:
            self.called = False

        def can_handle(self, _request):  # pragma: no cover - simple stub
            return True

        def handle(self, request, history=None):  # pragma: no cover - simple stub
            self.called = True
            assert history == []
            return ChatResponse(
                text="handled by common",
                grounding_chunks=[],
                rag_store_name="store-common",
                sources=["store-common"],
            )

    handler = StubHandler()
    app.dependency_overrides[get_common_chat_handler] = lambda: handler

    payload = {
        "sessionId": session_id,
        "query": "공통 문서 질문",
        "sources": ["store-common"],
    }
    response = test_client.post("/api/chat", json=payload)
    assert response.status_code == 200
    assert response.json()["text"] == "handled by common"
    assert handler.called is True

    app.dependency_overrides.pop(get_common_chat_handler, None)


def test_chat_includes_analyzer_clarification(test_client: TestClient, override_pipeline_client):
    session_id = test_client.post("/api/session").json()["sessionId"]
    override_pipeline_client.sessions[session_id] = {
        "sessionId": session_id,
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "questionHistory": [],
    }

    class StubAnalyzer:
        def analyze(self, query):  # pragma: no cover - simple stub
            return AnalyzerResult(
                filters=[MetadataFilter(key="priority", value="4", operator="EQUALS")],
                summaries=["우선순위=긴급"],
                success=True,
                confidence="low",
                clarification_needed=True,
                clarification=AnalyzerClarification(
                    reason="INVALID_PRIORITY",
                    message="옵션 중에서 선택",
                    options=["High", "Low"],
                ),
                known_context={},
            )

    app.dependency_overrides[get_query_filter_analyzer] = lambda: StubAnalyzer()

    payload = {
        "sessionId": session_id,
        "query": "긴급 우선순위 티켓",
        "sources": ["store-a"],
    }
    response = test_client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["clarificationNeeded"] is True
    assert data["clarification"]["message"] == "옵션 중에서 선택"
    assert data["filters"] == ["우선순위=긴급"]

    app.dependency_overrides.pop(get_query_filter_analyzer, None)
