from fastapi.testclient import TestClient


def test_common_products_via_service(test_client: TestClient):
    response = test_client.get("/api/common-products")
    assert response.status_code == 200
    assert response.json()["products"] == ["제품A", "제품B"]


def test_common_documents_endpoint(test_client: TestClient):
    response = test_client.get("/api/common-documents", params={"limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 1
    assert body["records"][0]["id"] == 123
    assert body["cursor"]["id"] == 999
