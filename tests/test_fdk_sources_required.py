from fastapi.testclient import TestClient


def test_fdk_chat_requires_sources(test_client: TestClient):
    res = test_client.post(
        "/api/fdk/v1/chat",
        json={
            "sessionId": "s1",
            "query": "hello",
        },
    )
    assert res.status_code == 400


def test_fdk_chat_requires_common_product_when_sources_present(test_client: TestClient):
    res = test_client.post(
        "/api/fdk/v1/chat",
        json={
            "sessionId": "s1",
            "query": "hello",
            "sources": ["tickets"],
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["error"] == "MISSING_COMMON_PRODUCT"


def test_fdk_chat_stream_requires_sources(test_client: TestClient):
    res = test_client.get(
        "/api/fdk/v1/chat/stream",
        params={
            "sessionId": "s1",
            "query": "hello",
        },
    )
    assert res.status_code == 400


def test_fdk_chat_stream_requires_common_product_when_sources_present(test_client: TestClient):
    res = test_client.get(
        "/api/fdk/v1/chat/stream",
        params={
            "sessionId": "s1",
            "query": "hello",
            "sources": "tickets",
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["error"] == "MISSING_COMMON_PRODUCT"


def test_fdk_chat_rejects_invalid_sources(test_client: TestClient):
    res = test_client.post(
        "/api/fdk/v1/chat",
        json={
            "sessionId": "s1",
            "query": "hello",
            "sources": ["invalid-source"],
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["error"] == "INVALID_SOURCES"
    assert "invalid-source" in body["detail"]["invalid"]


def test_fdk_chat_rejects_common_only_sources(test_client: TestClient):
    res = test_client.post(
        "/api/fdk/v1/chat",
        json={
            "sessionId": "s1",
            "query": "hello",
            "sources": ["common"],
            "commonProduct": "제품A",
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["error"] == "INVALID_SOURCES_COMBINATION"


def test_fdk_chat_rejects_store_name_combination(monkeypatch, test_client: TestClient):
    import app.api.routes.channel_fdk_v1 as channel_fdk_v1

    class StubSettings:
        gemini_store_tickets = "store-tickets"
        gemini_store_articles = None
        gemini_store_common = None
        gemini_common_store_name = None

    monkeypatch.setattr(channel_fdk_v1, "get_settings", lambda: StubSettings())

    res = test_client.post(
        "/api/fdk/v1/chat",
        json={
            "sessionId": "s1",
            "query": "hello",
            "sources": ["tickets", "store-tickets"],
            "commonProduct": "제품A",
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["error"] == "INVALID_SOURCES_COMBINATION"


def test_fdk_chat_stream_rejects_invalid_sources(test_client: TestClient):
    res = test_client.get(
        "/api/fdk/v1/chat/stream",
        params={
            "sessionId": "s1",
            "query": "hello",
            "sources": "invalid-source",
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["error"] == "INVALID_SOURCES"
