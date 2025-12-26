"""
Tests for POST /api/tickets/{ticket_id}/analyze

PR1 DoD:
- (1) 샘플 호출 시 200 OK
- (2) 응답이 ticket_analysis_v1 스키마 검증 통과
- (3) 잘못된 입력 → 400 + INVALID_INPUT_SCHEMA
- (4) 단위 테스트 최소 1개 포함
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.schema_validation import validate_output, clear_schema_cache


# Test constants
HEADERS = {"X-Tenant-ID": "test-tenant-123"}
VALID_TICKET_PAYLOAD = {
    "subject": "Cannot login to my account",
    "description": "<p>I'm having trouble logging in since yesterday.</p>",
    "description_text": "I'm having trouble logging in since yesterday.",
    "priority": 2,
    "status": 2,
    "tags": ["login", "urgent"],
    "custom_fields": {"product_name": "Enterprise Plan"},
    "conversations": [
        {
            "id": 1001,
            "body_text": "I tried resetting my password but it didn't work.",
            "incoming": True,
            "private": False,
            "created_at": "2025-01-01T10:00:00Z"
        }
    ]
}


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_schema_cache():
    """Clear schema cache before each test."""
    clear_schema_cache()
    yield
    clear_schema_cache()


class TestAnalyzeTicketEndpoint:
    """Tests for POST /api/tickets/{ticket_id}/analyze"""

    def test_analyze_valid_input_returns_200(self, client):
        """Valid input returns 200 with analysis_id and gate."""
        response = client.post(
            "/api/tickets/12345/analyze",
            json=VALID_TICKET_PAYLOAD,
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields exist
        assert "analysis_id" in data
        assert "ticket_id" in data
        assert "status" in data
        assert "gate" in data
        assert "analysis" in data
        assert "meta" in data

        # Check ticket_id matches
        assert data["ticket_id"] == "12345"

        # Check gate is valid enum
        assert data["gate"] in ["CONFIRM", "EDIT", "DECIDE", "TEACH"]

        # Check status
        assert data["status"] in ["completed", "failed", "partial"]

    def test_analyze_response_validates_against_schema(self, client):
        """Response validates against ticket_analysis_v1 schema."""
        response = client.post(
            "/api/tickets/12345/analyze",
            json=VALID_TICKET_PAYLOAD,
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()

        # Validate against schema
        is_valid = validate_output("ticket_analysis_v1", data)
        assert is_valid, "Response should validate against ticket_analysis_v1 schema"

    def test_analyze_minimal_input(self, client):
        """Minimal input (just required fields) works."""
        response = client.post(
            "/api/tickets/99999/analyze",
            json={},  # ticket_id comes from URL
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ticket_id"] == "99999"
        assert "analysis_id" in data

    def test_analyze_missing_tenant_id_returns_422(self, client):
        """Missing X-Tenant-ID header returns 422."""
        response = client.post(
            "/api/tickets/12345/analyze",
            json=VALID_TICKET_PAYLOAD,
            headers={}  # No tenant ID
        )

        # FastAPI returns 422 for missing required headers
        assert response.status_code == 422

    def test_analyze_with_conversations(self, client):
        """Input with conversations affects confidence/gate."""
        payload_with_convos = {
            **VALID_TICKET_PAYLOAD,
            "conversations": [
                {
                    "body_text": "First message",
                    "incoming": True,
                    "created_at": "2025-01-01T10:00:00Z"
                },
                {
                    "body_text": "Agent response",
                    "incoming": False,
                    "created_at": "2025-01-01T10:05:00Z"
                }
            ]
        }

        response = client.post(
            "/api/tickets/12345/analyze",
            json=payload_with_convos,
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()

        # With description + conversations, confidence should be higher
        analysis = data.get("analysis", {})
        confidence = analysis.get("confidence", 0)
        assert confidence >= 0.5, "Confidence should increase with more data"

    def test_analyze_without_description_low_confidence(self, client):
        """Input without description has low confidence."""
        response = client.post(
            "/api/tickets/12345/analyze",
            json={"subject": "Quick question"},  # No description
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()

        analysis = data.get("analysis", {})
        confidence = analysis.get("confidence", 1.0)
        # Without description, confidence should be lower
        assert confidence <= 0.5, "Confidence should be low without description"

    def test_analyze_meta_fields(self, client):
        """Meta fields are populated correctly."""
        response = client.post(
            "/api/tickets/12345/analyze",
            json=VALID_TICKET_PAYLOAD,
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()
        meta = data.get("meta", {})

        assert "prompt_version" in meta
        assert meta["prompt_version"] == "ticket_analysis_cot_v1"
        assert "created_at" in meta
        assert "latency_ms" in meta


class TestAnalyzeTicketHistory:
    """Tests for GET /api/tickets/{ticket_id}/analyses"""

    def test_get_analyses_returns_empty_list(self, client):
        """Get analyses returns empty list for new ticket."""
        response = client.get(
            "/api/tickets/12345/analyses",
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()

        assert data["ticket_id"] == "12345"
        assert data["analyses"] == []
        assert data["total"] == 0

    def test_get_analyses_with_limit(self, client):
        """Get analyses respects limit parameter."""
        response = client.get(
            "/api/tickets/12345/analyses?limit=5",
            headers=HEADERS
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5


class TestSchemaValidation:
    """Tests for schema validation utility."""

    def test_validate_output_valid_response(self):
        """validate_output returns True for valid response."""
        valid_response = {
            "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
            "ticket_id": "12345",
            "status": "completed",
            "gate": "CONFIRM",
            "analysis": {
                "narrative": {"summary": "Test summary"},
                "confidence": 0.85
            },
            "meta": {
                "llm_provider": "test",
                "created_at": "2025-01-01T00:00:00Z"
            }
        }

        is_valid = validate_output("ticket_analysis_v1", valid_response)
        assert is_valid is True

    def test_validate_output_invalid_gate(self):
        """validate_output returns False for invalid gate value."""
        invalid_response = {
            "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
            "ticket_id": "12345",
            "status": "completed",
            "gate": "INVALID_GATE",  # Invalid enum value
        }

        is_valid = validate_output("ticket_analysis_v1", invalid_response)
        assert is_valid is False

    def test_validate_output_missing_required_field(self):
        """validate_output returns False for missing required field."""
        incomplete_response = {
            "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
            # Missing: ticket_id, status, gate
        }

        is_valid = validate_output("ticket_analysis_v1", incomplete_response)
        assert is_valid is False
