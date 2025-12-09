import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.services.sync_service import SyncService, SyncOptions
from app.services.freshdesk_client import FreshdeskClient
from app.services.ingestion_service import TicketIngestionRecord

@pytest.mark.asyncio
async def test_sync_service_tickets_and_articles():
    # Mock FreshdeskClient
    mock_client = AsyncMock(spec=FreshdeskClient)
    
    # Mock EntityMapper
    # Use MagicMock for the main object so synchronous methods stay synchronous
    mock_entity_mapper = MagicMock()
    mock_entity_mapper.initialize = AsyncMock(return_value=None)
    mock_entity_mapper.map_ticket_entities = AsyncMock(return_value={
        "responder_label": "Agent Smith",
        "group_label": "Support",
        "company_label": "Acme Corp",
        "requester_label": "John Doe",
        "product_label": "Widget",
    })
    mock_entity_mapper.map_article_entities = AsyncMock(return_value={
        "category_label": "General",
        "folder_label": "FAQ",
    })
    
    # Force get_field_choices to be synchronous and return a dict
    def get_field_choices_side_effect(field_type):
        if field_type == "status":
            return {2: "Custom Open"}
        return {}
    mock_entity_mapper.get_field_choices.side_effect = get_field_choices_side_effect
    
    # Force get_stats to be synchronous
    mock_entity_mapper.get_stats.return_value = {}
    
    # Mock IngestionService
    mock_client.get_all_tickets.return_value = [
        {
            "id": 1,
            "subject": "Test Ticket",
            "description_text": "Help me",
            "status": 2,
            "priority": 1,
            "source": 1,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z",
            "tags": ["urgent"],
            "responder_id": 1001,
            "requester_id": 2001,
        }
    ]
    mock_client.get_all_conversations.return_value = [
        {
            "id": 101,
            "body_text": "I need help",
            "incoming": True,
            "created_at": "2023-01-01T00:00:00Z",
        }
    ]
    mock_client.get_all_articles.return_value = [
        {
            "id": 201,
            "title": "How to use",
            "description_text": "Just click it",
            "status": 2,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z",
            "folder_id": 301,
            "category_id": 401,
        }
    ]

    # Patch EntityMapper in SyncService
    with patch("app.services.sync_service.EntityMapper", return_value=mock_entity_mapper):
        service = SyncService(mock_client, tenant_id="test")
        
        # Mock upload callback
        uploaded_docs = []
        async def upload_callback(docs):
            uploaded_docs.extend(docs)
        
        # Run sync
        result = await service.sync(
            options=SyncOptions(include_tickets=True, include_articles=True),
            upload_callback=upload_callback
        )
        
        # Verify results
        assert result.tickets_count == 1
        assert result.articles_count == 1
        assert len(uploaded_docs) == 2
        
        # Verify ticket doc
        ticket_doc = next(d for d in uploaded_docs if d.type == "ticket")
        assert ticket_doc.title == "Test Ticket"
        assert ticket_doc.metadata["status"] == "Custom Open"
        assert ticket_doc.metadata["responder"] == "Agent Smith"
        
        # Verify article doc
        article_doc = next(d for d in uploaded_docs if d.type == "article")
        assert article_doc.title == "How to use"
        assert article_doc.metadata["category"] == "General"