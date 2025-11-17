from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings


class PipelineClientError(Exception):
    def __init__(self, status_code: int, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {"error": message}


class PipelineClient:
    """기존 Google File Search 파이프라인(Node 서버)와 통신하기 위한 HTTP 클라이언트."""

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def _request(self, method: str, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(method, url, json=json, timeout=self.timeout)
        except httpx.RequestError as exc:
            raise PipelineClientError(status.HTTP_502_BAD_GATEWAY, f"Pipeline 서버에 연결할 수 없습니다: {exc}") from exc

        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": response.text or response.reason_phrase}
            message = payload.get("error") or response.reason_phrase or "Pipeline 요청 실패"
            raise PipelineClientError(response.status_code, message, payload)

        try:
            return response.json()
        except ValueError as exc:
            raise PipelineClientError(status.HTTP_502_BAD_GATEWAY, "Pipeline 응답을 JSON으로 파싱하지 못했습니다") from exc

    def create_session(self) -> Dict[str, Any]:
        return self._request("POST", "/session")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/session/{session_id}")

    def chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/chat", json=payload)

    def get_status(self) -> Dict[str, Any]:
        return self._request("GET", "/status")

    def list_common_products(self) -> Dict[str, Any]:
        return self._request("GET", "/common-products")

    def trigger_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/sync", json=payload)


@lru_cache
def get_pipeline_client() -> PipelineClient:
    settings = get_settings()
    if not settings.pipeline_base_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Pipeline base URL이 설정되지 않았습니다")
    return PipelineClient(settings.pipeline_base_url)
