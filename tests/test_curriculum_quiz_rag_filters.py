from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import pytest

from app.api.routes import curriculum as curriculum_routes


@dataclass
class _DummyModule:
    name_ko: str
    description: str
    target_product_id: str
    kb_category_slug: Optional[str]


@dataclass
class _DummyContents:
    sections: dict[str, list[Any]]


@pytest.mark.anyio
def test_quiz_rag_supplement_applies_product_metadata_filters(test_client, monkeypatch):
    module_id = UUID("11111111-1111-1111-1111-111111111111")
    captured: dict[str, Any] = {}

    class _DummyRepo:
        async def get_questions(self, *, module_id: UUID, active_only: bool = True):  # noqa: ARG002
            return []

        async def get_module_by_id(self, _module_id: UUID):
            assert _module_id == module_id
            return _DummyModule(
                name_ko="통합 워크스페이스의 이해",
                description="Freshdesk Omni의 통합 워크스페이스 개요",
                target_product_id="freshdesk_omni",
                kb_category_slug="omnichannel",
            )

        async def get_module_contents(self, _module_id: UUID):
            assert _module_id == module_id
            # 콘텐츠가 부족하도록 비워서 RAG 폴백을 타게 만든다.
            return _DummyContents(sections={})

    class _DummySearchClient:
        async def search(
            self,
            *,
            query: str,  # noqa: ARG002
            store_names: list[str],  # noqa: ARG002
            metadata_filters=None,
            conversation_history=None,  # noqa: ARG002
            system_instruction: str | None = None,  # noqa: ARG002
        ):
            captured["metadata_filters"] = metadata_filters
            return {"text": "X" * 600}

    async def _stub_generate_quiz_questions(
        _module_id: UUID, _module_name: str, _module_desc: str = "", _module_content: str = ""
    ):
        captured["module_content"] = _module_content
        return []

    class _DummySettings:
        gemini_store_common = "store-common"

    monkeypatch.setattr(curriculum_routes, "get_curriculum_repository", lambda: _DummyRepo(), raising=True)
    monkeypatch.setattr(curriculum_routes, "_get_file_search_client", lambda: _DummySearchClient(), raising=True)
    monkeypatch.setattr(curriculum_routes, "_generate_quiz_questions", _stub_generate_quiz_questions, raising=True)
    monkeypatch.setattr(curriculum_routes, "_get_settings", lambda: _DummySettings(), raising=True)

    response = test_client.get(f"/api/curriculum/modules/{module_id}/questions")
    assert response.status_code == 200

    filters = captured.get("metadata_filters")
    assert filters, "RAG 검색에 metadata_filters가 전달되지 않았습니다."
    assert any(getattr(f, "key", None) == "product" and getattr(f, "value", None) == "freshdesk_omni" for f in filters)
    assert any(getattr(f, "key", None) == "category" and getattr(f, "value", None) == "omnichannel" for f in filters)

    module_content = captured.get("module_content", "")
    assert "RAG Retrieved Content" in module_content
