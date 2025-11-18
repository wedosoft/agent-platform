from __future__ import annotations

import json
import logging
from typing import Any, Iterable, List, Optional

from google import genai

from app.models.metadata import MetadataFilter

LOGGER = logging.getLogger(__name__)


def _build_metadata_expression(filters: Optional[Iterable[MetadataFilter]]) -> Optional[str]:
    if not filters:
        return None
    operator_map = {
        "EQUALS": "=",
        "GREATER_THAN": ">",
        "LESS_THAN": "<",
    }
    expressions: List[str] = []
    for metadata in filters:
        if not metadata.key or metadata.value is None:
            continue
        if metadata.operator == "IN":
            values = [value.strip() for value in metadata.value.split(",") if value.strip()]
            if not values:
                continue
            if len(values) == 1:
                escaped = values[0].replace('"', '\"')
                expressions.append(f"{metadata.key} = \"{escaped}\"")
            else:
                clauses = []
                for value in values:
                    escaped_value = value.replace('"', '\"')
                    clauses.append(f"{metadata.key} = \"{escaped_value}\"")
                expressions.append("(" + " OR ".join(clauses) + ")")
            continue
        operator = operator_map.get(metadata.operator or "EQUALS", "=")
        escaped_value = metadata.value.replace('"', '\"')
        expressions.append(f"{metadata.key} {operator} \"{escaped_value}\"")

    if not expressions:
        return None
    return " AND ".join(expressions)


class GeminiClientError(RuntimeError):
    pass


class GeminiRetryableError(GeminiClientError):
    """Raised when a Gemini request can be retried safely."""
    pass


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        primary_model: str,
        fallback_model: Optional[str] = None,
    ) -> None:
        if not api_key:
            raise GeminiClientError("Gemini API key is required")
        if not primary_model:
            raise GeminiClientError("Gemini model name is required")
        self.client = genai.Client(api_key=api_key)
        self.models = [primary_model]
        if fallback_model and fallback_model not in self.models:
            self.models.append(fallback_model)

    def search(
        self,
        *,
        query: str,
        store_names: List[str],
        metadata_filters: Optional[List[MetadataFilter]] = None,
        conversation_history: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        if not store_names:
            raise GeminiClientError("At least one file search store name is required")

        metadata_expression = _build_metadata_expression(metadata_filters)

        history_parts = [
            {
                "role": "user",
                "parts": [{"text": entry}],
            }
            for entry in (conversation_history or [])
            if entry.strip()
        ]
        contents = history_parts + [
            {
                "role": "user",
                "parts": [{"text": query}],
            }
        ]

        last_error: Optional[Exception] = None
        for model_name in self.models:
            try:
                # TODO: File Search 툴 구성은 google-genai 버전에 따라 달라지므로
                # 현재 버전에서는 우선 기본 텍스트 생성만 사용한다.
                # metadata_expression은 추후 시스템 프롬프트 등에 녹이는 방향으로 개선 가능.
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                text = getattr(response, "text", None)
                if not text and getattr(response, "candidates", None):
                    candidate = response.candidates[0]
                    parts = getattr(candidate, "content", None)
                    if parts and getattr(parts, "parts", None):
                        first_part = parts.parts[0]
                        text = getattr(first_part, "text", "")
                grounding_chunks: List[Any] = []
                chunks = None
                if getattr(response, "candidates", None):
                    candidate = response.candidates[0]
                    metadata = getattr(candidate, "grounding_metadata", None)
                    chunks = getattr(metadata, "grounding_chunks", None)
                if chunks:
                    for chunk in chunks:
                        if hasattr(chunk, "to_dict"):
                            grounding_chunks.append(chunk.to_dict())
                        else:
                            try:
                                grounding_chunks.append(json.loads(json.dumps(chunk)))
                            except Exception:
                                grounding_chunks.append(str(chunk))
                return {
                    "text": text or "검색 결과를 가져오지 못했습니다. 다시 시도해 주세요.",
                    "grounding_chunks": grounding_chunks,
                    "store_names": store_names,
                    "applied_filters": metadata_filters or [],
                }
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.warning("Gemini model %s failed: %s", model_name, exc)
                last_error = exc
        raise GeminiClientError("Gemini 검색 실패") from last_error
