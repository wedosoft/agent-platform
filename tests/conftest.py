import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services import pipeline_client as pipeline_client_module
from app.services import session_repository as session_repository_module


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


@pytest.fixture(autouse=True)
def override_pipeline_client():
    dummy = DummyPipelineClient()
    app.dependency_overrides[pipeline_client_module.get_pipeline_client] = lambda: dummy
    yield dummy
    app.dependency_overrides.pop(pipeline_client_module.get_pipeline_client, None)


@pytest.fixture()
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_session_repository():
    settings = get_settings()
    repo = session_repository_module.InMemorySessionRepository(settings.session_ttl_minutes * 60)
    app.dependency_overrides[session_repository_module.get_session_repository] = lambda: repo
    yield repo
    app.dependency_overrides.pop(session_repository_module.get_session_repository, None)
