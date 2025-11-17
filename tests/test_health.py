from fastapi.testclient import TestClient


def test_health_endpoint(test_client: TestClient):
    response = test_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
