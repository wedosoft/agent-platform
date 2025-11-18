import asyncio

from app.services.freshdesk_metadata import FreshdeskMetadataService


def test_freshdesk_metadata_resolves_priority():
    service = FreshdeskMetadataService(ttl_hours=0)
    priority = asyncio.run(service.resolve_priority_label("High"))
    assert priority == 3


def test_freshdesk_metadata_resolves_status():
    service = FreshdeskMetadataService(ttl_hours=0)
    status = asyncio.run(service.resolve_status_label("Closed"))
    assert status == 5
