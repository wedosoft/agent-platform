from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)


class LegacyRouteObservabilityMiddleware(BaseHTTPMiddleware):
    """
    레거시(`/api/chat*`) 호출을 운영 환경에서 관측하기 위한 미들웨어.

    - 응답/동작/SSE 포맷을 변경하지 않습니다.
    - API key 등 민감 정보는 로깅하지 않습니다.
    - request_id는 RequestIdMiddleware의 contextvar/log filter를 통해 자동 포함됩니다.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path not in {"/api/chat", "/api/chat/stream"}:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        tenant_id = (request.headers.get("X-Tenant-ID") or "").strip()
        platform = (request.headers.get("X-Platform") or "").strip().lower()
        has_tenant_headers = bool(tenant_id and platform)

        query_len: int | None = None
        if path == "/api/chat/stream":
            query = (request.query_params.get("query") or "").strip()
            query_len = len(query)

        logger.info(
            "legacy_request route=%s method=%s status=%s elapsed_ms=%s has_tenant_headers=%s tenant_id=%s platform=%s query_len=%s",
            path,
            request.method,
            response.status_code,
            elapsed_ms,
            has_tenant_headers,
            tenant_id or "-",
            platform or "-",
            query_len if query_len is not None else "-",
        )
        return response

