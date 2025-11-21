import os
from typing import Any, Dict, List

import pytest

from app.main import app
from app.models.analyzer import AnalyzerResult
from app.models.metadata import MetadataFilter
from app.services.agent_chat_service import AgentChatService, get_agent_chat_service
from app.services.tenant_registry import get_tenant_registry
@pytest.fixture(autouse=True)
def reset_tenant_registry(monkeypatch):
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "tenants.local.json"))
    monkeypatch.setenv("AGENT_PLATFORM_TENANT_CONFIG_PATH", config_path)
    get_tenant_registry.cache_clear()
    yield
    get_tenant_registry.cache_clear()



class _StubGeminiClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def search(self, **kwargs):  # pragma: no cover - simple stub
        self.calls.append(kwargs)
        return {
            "text": "stubbed gemini response",
            "grounding_chunks": [],
            "store_names": kwargs.get("store_names", []),
            "applied_filters": kwargs.get("metadata_filters", []),
        }


class _StubAnalyzer:
    async def analyze(self, *_args, **_kwargs) -> AnalyzerResult:  # pragma: no cover - simple stub
        return AnalyzerResult(
            filters=[MetadataFilter(key="priority", value="4", operator="EQUALS")],
            summaries=["우선순위=긴급"],
            success=True,
            confidence="medium",
            clarification_needed=False,
            clarification=None,
            known_context={},
        )


@pytest.fixture
def stub_agent_service():
    service = AgentChatService(
        gemini_client=_StubGeminiClient(),
        analyzer=_StubAnalyzer(),
        freshdesk_search=None,
    )
    app.dependency_overrides[get_agent_chat_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_agent_chat_service, None)


@pytest.fixture
def tenant_id():
    registry = get_tenant_registry()
    return next(iter(registry.list().keys()))


def test_create_agent_session(test_client, tenant_id):
    response = test_client.post(f"/api/agents/{tenant_id}/session")
    assert response.status_code == 201
    payload = response.json()
    assert payload["tenantId"] == tenant_id
    assert payload["ttlMinutes"] > 0


def test_agent_chat_applies_common_product_filter(test_client, stub_agent_service, tenant_id):
    session = test_client.post(f"/api/agents/{tenant_id}/session").json()
    session_id = session["sessionId"]

    payload = {
        "sessionId": session_id,
        "query": "Freshservice 티켓 자산 연동",
        "commonProduct": "custom-product",
    }
    response = test_client.post(f"/api/agents/{tenant_id}/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["filters"][0] == "제품=custom-product"

    gemini_calls = stub_agent_service.gemini_client.calls  # type: ignore[attr-defined]
    assert gemini_calls, "Gemini 클라이언트가 호출되어야 합니다"
    metadata_filters = gemini_calls[0]["metadata_filters"]
    assert any(f.key == "product" and f.value == "custom-product" for f in metadata_filters)
    assert any(f.key == "priority" for f in metadata_filters), "분석기 필터가 유지되어야 합니다"