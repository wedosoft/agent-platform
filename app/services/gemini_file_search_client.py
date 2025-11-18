from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

import httpx

from app.models.metadata import MetadataFilter
from app.services.gemini_client import GeminiClientError, _build_metadata_expression

LOGGER = logging.getLogger(__name__)


class GeminiFileSearchClient:
    """Gemini File Search 전용 REST 클라이언트.

    google-genai Python SDK가 아직 file_search 툴 타입을 노출하지 않기 때문에
    공식 REST 엔드포인트(v1beta/models/*:generateContent)를 직접 호출합니다.
    """

    def __init__(
        self,
        api_key: str,
        primary_model: str,
        fallback_model: Optional[str] = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise GeminiClientError("Gemini API key is required")
        if not primary_model:
            raise GeminiClientError("Gemini model name is required")
        self.api_key = api_key
        self.models: List[str] = [primary_model]
        if fallback_model and fallback_model not in self.models:
            self.models.append(fallback_model)
        self.timeout = timeout

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
            if isinstance(entry, str) and entry.strip()
        ]
        contents = history_parts + [
            {
                "role": "user",
                "parts": [{"text": query}],
            }
        ]

        last_error: Optional[Exception] = None
        for model_name in self.models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            
            # v1beta API 공식 스키마: fileSearch (camelCase) + fileSearchStoreNames
            file_search_tool: dict[str, Any] = {
                "fileSearch": {
                    "fileSearchStoreNames": store_names
                }
            }
            
            if metadata_expression:
                file_search_tool["fileSearch"]["metadataFilter"] = metadata_expression
            
            body: dict[str, Any] = {
                "contents": contents,
                "tools": [file_search_tool],
            }

            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            }

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, headers=headers, json=body)
                if response.status_code >= 400:
                    last_error = GeminiClientError(
                        f"Gemini REST error {response.status_code}: {response.text}"
                    )
                    LOGGER.warning("Gemini REST %s failed: %s", model_name, last_error)
                    continue
                data = response.json()
            except Exception as exc:  # pragma: no cover - 네트워크 오류
                last_error = exc
                LOGGER.warning("Gemini REST %s request failed: %s", model_name, exc)
                continue

            text = self._extract_text(data)
            grounding_chunks = self._extract_grounding_chunks(data)
            return {
                "text": text or "검색 결과를 가져오지 못했습니다. 다시 시도해 주세요.",
                "grounding_chunks": grounding_chunks,
                "store_names": store_names,
                "applied_filters": metadata_filters or [],
            }

        raise GeminiClientError("Gemini 검색 실패") from last_error

    def _extract_text(self, payload: dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            return text
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        first = candidates[0] or {}
        content = first.get("content") or {}
        parts = content.get("parts") or []
        if parts and isinstance(parts[0], dict):
            return str(parts[0].get("text") or "")
        # 안전 장치: 직렬화 가능한 경우 문자열로 변환
        try:
            return json.dumps(first)
        except Exception:  # pragma: no cover - 디버그용
            return ""

    def _extract_grounding_chunks(self, payload: dict[str, Any]) -> List[Any]:
        candidates = payload.get("candidates") or []
        if not candidates:
            return []
        first = candidates[0] or {}
        metadata = first.get("groundingMetadata") or first.get("grounding_metadata") or {}
        chunks = (
            metadata.get("groundingChunks")
            or metadata.get("grounding_chunks")
            or []
        )
        # JSON 직렬화 가능한 형태만 돌려주도록 방어
        safe_chunks: List[Any] = []
        for chunk in chunks:
            if isinstance(chunk, (dict, list, str, int, float, bool)) or chunk is None:
                safe_chunks.append(chunk)
                continue
            try:
                safe_chunks.append(json.loads(json.dumps(chunk)))
            except Exception:  # pragma: no cover - 예외적인 타입
                safe_chunks.append(str(chunk))
        return safe_chunks

