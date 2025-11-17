from typing import List

from app.models.common_documents import (
    CommonDocumentsConfig,
    CommonDocumentRecord,
    CommonDocumentsFetchOptions,
)
from app.services.common_documents import CommonDocumentsService, CommonDocumentsRepository


class DummyRepository(CommonDocumentsRepository):
    def __init__(self) -> None:
        self.records: List[CommonDocumentRecord] = []

    def fetch_documents(self, options: CommonDocumentsFetchOptions):  # pragma: no cover - unused in chunk tests
        return None

    def count_documents(self, product=None):  # pragma: no cover - unused in chunk tests
        return 0

    def list_products(self):  # pragma: no cover - unused in chunk tests
        return []


def build_service(summary_enabled: bool = False) -> CommonDocumentsService:
    config = CommonDocumentsConfig(
        url="https://example.supabase.co",
        serviceRoleKey="key",
        batchSize=2,
        languages=["ko"],
        summaryEnabled=summary_enabled,
    )
    repo = DummyRepository()
    return CommonDocumentsService(repo, config)


def test_to_chunks_skips_missing_content():
    service = build_service()
    records = [
        {"id": 1, "title_ko": "제목", "content_text_en": "hello"},
        {"id": 2, "title_ko": "", "content_text_ko": "본문"},
    ]
    chunks = service.to_chunks(records)
    assert chunks == []


def test_to_chunks_generates_chunks_with_overlap():
    service = build_service(summary_enabled=True)
    text = "0123456789" * 30
    record = {"id": 10, "title_ko": "제목", "content_text_ko": text, "product": "공통"}
    chunks = service.to_chunks([record], languages=["ko"])
    assert chunks, "chunk list should not be empty"
    assert chunks[0].metadata["documentId"] == 10
    assert chunks[0].metadata["language"] == "ko"
    assert chunks[0].summary
