from fastapi.testclient import TestClient


def test_create_session(test_client: TestClient):
    response = test_client.post("/api/session")
    assert response.status_code == 201
    payload = response.json()
    assert payload["sessionId"].startswith("session-")
    assert payload["ttlMinutes"] == 30


def test_get_session(test_client: TestClient):
    create = test_client.post("/api/session")
    session_id = create.json()["sessionId"]

    response = test_client.get(f"/api/session/{session_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sessionId"] == session_id
    assert payload["questionHistory"] == []
