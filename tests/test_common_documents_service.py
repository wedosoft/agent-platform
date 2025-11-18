from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Iterator, List

import pytest

from app.models.common_documents import CommonDocumentCursor
from app.services.common_documents import (
    CommonDocumentsConfig,
    CommonDocumentsError,
    CommonDocumentsService,
)


@dataclass
class StubResponse:
    data: List[dict]
    count: int | None = None
    error: Exception | None = None


class StubQuery:
    def __init__(self, responses: Iterator[StubResponse]):
        self.responses = responses

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def or_(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def range(self, *_args, **_kwargs):
        return self

    def execute(self):
        try:
            response = next(self.responses)
        except StopIteration:  # pragma: no cover - indicates broken test setup
            raise AssertionError("No more responses available")
        return SimpleNamespace(data=response.data, count=response.count, error=response.error)


class StubSupabaseClient:
    def __init__(self, responses: List[StubResponse]):
        self._responses = iter(responses)

    def table(self, _name: str):
        return StubQuery(self._responses)


@pytest.fixture
def common_config() -> CommonDocumentsConfig:
    return CommonDocumentsConfig(
        url="https://example.supabase.co",
        service_role_key="service-key",
        table_name="documents",
        batch_size=2,
    )


def test_fetch_documents_returns_cursor(common_config: CommonDocumentsConfig):
    responses = [
        StubResponse(
            data=[
                {"id": 1, "updated_at": "2025-01-01T00:00:00Z"},
                {"id": 2, "updated_at": "2025-01-02T00:00:00Z"},
            ]
        )
    ]
    service = CommonDocumentsService(common_config, client=StubSupabaseClient(responses))
    result = service.fetch_documents(limit=2)
    assert len(result.records) == 2
    assert isinstance(result.cursor, CommonDocumentCursor)
    assert result.cursor.id == 2
    assert result.cursor.updated_at == "2025-01-02T00:00:00Z"


def test_count_documents_uses_response_count(common_config: CommonDocumentsConfig):
    responses = [StubResponse(data=[], count=42)]
    service = CommonDocumentsService(common_config, client=StubSupabaseClient(responses))
    assert service.count_documents() == 42


def test_list_products_deduplicates(common_config: CommonDocumentsConfig):
    responses = [
        StubResponse(data=[{"product": "Alpha"}, {"product": "beta"}, {"product": "Alpha"}]),
        StubResponse(data=[]),
    ]
    service = CommonDocumentsService(common_config, client=StubSupabaseClient(responses))
    assert service.list_products() == ["Alpha", "beta"]


def test_service_raises_on_supabase_error(common_config: CommonDocumentsConfig):
    responses = [StubResponse(data=[], error=Exception("boom"))]
    service = CommonDocumentsService(common_config, client=StubSupabaseClient(responses))
    with pytest.raises(CommonDocumentsError):
        service.fetch_documents()
