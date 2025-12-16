from __future__ import annotations

from typing import Any

from app.services.supabase_kb_client import KBClient


class _QueryBuilder:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    def execute(self):
        self._state["executed"] = True

        class _Resp:
            data = [{"id": "doc-1"}]

        return _Resp()


class _SelectBuilder:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    def select(self, _cols: str):
        self._state["calls"].append("select")
        return self

    def eq(self, key: str, value: Any):
        self._state["calls"].append(f"eq:{key}={value}")
        return self

    def limit(self, n: int):
        self._state["calls"].append(f"limit:{n}")
        return self

    def text_search(self, column: str, query: str, _opts=None):  # noqa: ANN001
        self._state["calls"].append(f"text_search:{column}={query}")
        return _QueryBuilder(self._state)


class _FakeSupabase:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    def table(self, name: str):
        self._state["calls"].append(f"table:{name}")
        return _SelectBuilder(self._state)


def test_kb_text_search_calls_limit_before_text_search():
    state: dict[str, Any] = {"calls": []}
    kb = KBClient.__new__(KBClient)
    kb.client = _FakeSupabase(state)  # type: ignore[assignment]

    result = KBClient.text_search(kb, "테스트", product_filter=None, limit=3)
    assert result and result[0]["id"] == "doc-1"

    calls = state["calls"]
    assert "limit:3" in calls
    assert any(c.startswith("text_search:") for c in calls)
    assert calls.index("limit:3") < next(i for i, c in enumerate(calls) if c.startswith("text_search:"))

