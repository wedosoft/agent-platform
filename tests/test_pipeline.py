from fastapi.testclient import TestClient


def test_status_endpoint(test_client: TestClient):
    response = test_client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert "store-default" in body["availableSources"]


def test_common_products_endpoint(test_client: TestClient):
    response = test_client.get("/api/common-products")
    assert response.status_code == 200
    assert response.json()["products"] == ["제품A", "제품B"]


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
