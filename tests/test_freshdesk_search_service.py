import asyncio

from app.models.analyzer import AnalyzerResult
from app.models.metadata import MetadataFilter
from app.models.entity import EntityMatch, EntityResolutionResult
from app.services.freshdesk_search_service import FreshdeskSearchService


class StubClient:
    def __init__(self) -> None:
        self.last_query = None

    async def search_tickets(self, query):
        self.last_query = query
        return {
            "results": [
                {
                    "id": 101,
                    "subject": "Test Ticket",
                    "status_name": "Open",
                    "priority_name": "High",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "requester": {"name": "Alice"},
                    "responder": {"name": "Bob"},
                    "description_text": "Example description",
                }
            ],
            "total": 1,
        }


class StubResolver:
    async def resolve(self, term, include_contacts=True, include_agents=True):
        matches = []
        if include_contacts:
            matches.append(EntityMatch(id=11, type="contact", name=term, confidence=0.9))
        if include_agents:
            matches.append(EntityMatch(id=22, type="agent", name=term, confidence=0.8))
        return EntityResolutionResult(matches=matches, clarification_needed=False)


class StubMetadataService:
    async def resolve_category_id(self, label: str):  # pragma: no cover - not used in this test
        return None

    async def resolve_folder_id(self, label: str):  # pragma: no cover - not used in this test
        return None


async def run_search():
    filters = [
        MetadataFilter(key="priority", value="4"),
        MetadataFilter(key="status", value="2"),
        MetadataFilter(key="createdAt", operator="GREATER_THAN", value="2025-01-01T00:00:00Z"),
    ]
    analyzer_result = AnalyzerResult(
        filters=filters,
        summaries=[],
        success=True,
        confidence="high",
        clarification_needed=False,
        clarification=None,
        known_context={"contactQuery": "Alice", "agentQuery": "Bob"},
    )
    service = FreshdeskSearchService(
        client=StubClient(),
        entity_resolver=StubResolver(),
        metadata_service=StubMetadataService(),
    )
    return await service.search_with_filters(analyzer_result)


def test_freshdesk_search_service_builds_query():
    result = asyncio.run(run_search())
    assert result.ticket_ids == [101]
    assert result.plan["appliedFilters"]
    assert result.plan["entityMappings"]
    assert "requester_id" in result.query_string
    assert result.tickets[0]["requester"] == "Alice"
