from fastapi.testclient import TestClient


def test_legacy_chat_stream_routes_through_multitenant_handler_when_tenant_headers_present(test_client: TestClient):
    from app.main import app
    from app.services.multitenant_chat_handler import get_multitenant_chat_handler

    class StubMultitenantHandler:
        async def stream_handle(self, request, tenant, *, history=None, additional_filters=None):
            yield {
                "event": "result",
                "data": {"text": "ok", "groundingChunks": []},
            }

    app.dependency_overrides[get_multitenant_chat_handler] = lambda: StubMultitenantHandler()
    try:
        res = test_client.get(
            "/api/chat/stream",
            params={"sessionId": "s-stream-1", "query": "hi"},
            headers={
                "X-Tenant-ID": "t1",
                "X-Platform": "web",
                "X-API-Key": "any",
            },
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")
        assert "event: result" in res.text
        assert '"text": "ok"' in res.text
    finally:
        app.dependency_overrides.pop(get_multitenant_chat_handler, None)


def test_multitenant_chat_stream_uses_multitenant_handler(test_client: TestClient):
    from app.main import app
    from app.services.multitenant_chat_handler import get_multitenant_chat_handler

    class StubMultitenantHandler:
        async def stream_handle(self, request, tenant, *, history=None, additional_filters=None):
            yield {
                "event": "result",
                "data": {"text": "ok", "groundingChunks": []},
            }

    app.dependency_overrides[get_multitenant_chat_handler] = lambda: StubMultitenantHandler()
    try:
        res = test_client.get(
            "/api/multitenant/chat/stream",
            params={"sessionId": "s-stream-2", "query": "hi"},
            headers={
                "X-Tenant-ID": "t1",
                "X-Platform": "web",
                "X-API-Key": "any",
            },
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")
        assert "event: result" in res.text
        assert '"text": "ok"' in res.text
    finally:
        app.dependency_overrides.pop(get_multitenant_chat_handler, None)

