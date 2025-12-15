"""003-ticket-analysis-speed 관련 테스트

- source 필드 제안 제거
- assist 분석 시 conversations 전체 수집(페이지네이션) 포함

주의: 외부 API/LLM 호출은 monkeypatch로 차단한다.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest


@pytest.mark.anyio
async def test_analyzer_filters_out_source_field_proposals(monkeypatch):
    """Analyzer 단계에서 source 제안이 최종 analysis_result에 남지 않아야 한다."""

    from app.agents import analyzer as analyzer_module

    async def fake_analyze_ticket(_self, _ticket_context: Dict[str, Any], response_tone: str = "formal") -> Dict[str, Any]:
        return {
            "intent": "inquiry",
            "sentiment": "neutral",
            "summary": "요약",
            "key_entities": [],
            "field_proposals": [
                {
                    "field_name": "source",
                    "field_label": "Source",
                    "proposed_value": 2,
                    "reason": "테스트",
                },
                {
                    "field_name": "priority",
                    "field_label": "Priority",
                    "proposed_value": 3,
                    "reason": "테스트",
                },
            ],
        }

    # LLM 호출 차단
    monkeypatch.setattr(analyzer_module.LLMAdapter, "analyze_ticket", fake_analyze_ticket)

    state: Dict[str, Any] = {
        "ticket_context": {"ticketId": "123", "subject": "s", "description": "d"},
        "response_tone": "formal",
        "selected_fields": [],
    }

    out = await analyzer_module.analyze_ticket(state)
    proposals = (out.get("analysis_result") or {}).get("field_proposals") or []

    assert all(p.get("field_name") != "source" for p in proposals)


@pytest.mark.anyio
async def test_assist_enrich_ticket_context_adds_conversations(monkeypatch):
    """assist 라우트에서 ticket_context에 conversations가 포함되어야 한다.

    구현은 별도 helper 함수(`_enrich_ticket_context_with_conversations`) 기준으로 테스트한다.
    """

    from app.api.routes import assist as assist_routes

    calls: List[int] = []

    async def fake_get_all_conversations(self, ticket_id: int):
        calls.append(ticket_id)
        # 30개 초과를 가정
        return [{"body_text": f"c{i}", "incoming": True, "private": False, "created_at": None, "user_id": 1} for i in range(35)]

    monkeypatch.setattr(assist_routes.FreshdeskClient, "get_all_conversations", fake_get_all_conversations, raising=False)

    ticket_context = {
        "ticketId": "777",
        "subject": "테스트",
        "description": "테스트",
    }

    enriched = await assist_routes._enrich_ticket_context_with_conversations(
        ticket_context,
        freshdesk_domain="company.freshdesk.com",
        freshdesk_api_key="dummy",
        tenant_id="test-tenant",
    )

    assert calls == [777]
    assert "conversations" in enriched
    assert len(enriched["conversations"]) == 35
