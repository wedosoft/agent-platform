from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_status_endpoint(test_client: TestClient):
    settings = get_settings()
    original_store = settings.gemini_common_store_name
    settings.gemini_common_store_name = "store-common"

    response = test_client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert "store-common" in body["availableSources"]

    settings.gemini_common_store_name = original_store


def test_sync_endpoint(test_client: TestClient):
    payload = {
        "includeTickets": True,
        "includeCommonDocuments": True,
        "commonProduct": "제품A",
    }
    response = test_client.post("/api/sync", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["ticketCount"] == 10
    assert body["commonDocumentCount"] == 2
