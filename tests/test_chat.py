from fastapi.testclient import TestClient


def test_chat_flow(test_client: TestClient):
    session_id = test_client.post("/api/session").json()["sessionId"]
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
