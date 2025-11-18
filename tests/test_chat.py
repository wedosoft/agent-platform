from fastapi.testclient import TestClient

from app.main import app
from app.models.session import ChatResponse
from app.services.common_chat_handler import get_common_chat_handler


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
