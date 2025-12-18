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


def test_fdk_chat_stream_requires_sources(test_client: TestClient):
    res = test_client.get(
        "/api/fdk/v1/chat/stream",
        params={
            "sessionId": "s1",
            "query": "hello",
        },
    )
    assert res.status_code == 400


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
