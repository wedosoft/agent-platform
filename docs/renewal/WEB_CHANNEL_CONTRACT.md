# WEB 채널 계약 (단일 참조 문서)

> 목적: WEB 채널 BFF(`/api/web/v1/*`)의 **입력/인증/에러 계약을 명확히 고정**해서, 프론트/채널 구현 실수와 “암묵적 동작”을 줄입니다.
>
> 구현 스펙(단일 소스): `app/api/routes/channel_web_v1.py`
>
> OpenAPI 확인: 로컬 실행 후 `/docs` 또는 `/openapi.json`

## 공통: 멀티테넌트 인증 헤더

아래 엔드포인트는 기본적으로 `get_tenant_context`를 사용하므로 **인증 헤더가 필수**입니다.

- `X-Tenant-ID`: 테넌트 식별자(예: `wedosoft`)
- `X-Platform`: 플랫폼(예: `web`, `freshdesk`, `zendesk`)
- `X-API-Key`: 플랫폼별 API key (검증 실패 시 403)
- `X-Domain`: (옵션) 검증 도메인 지정

## 엔드포인트

### 1) POST `/api/web/v1/chat`

#### 요청(JSON)

- `sessionId`: string (필수)
- `query`: string (필수)
- `sources`: string[] (옵션)
- `product` 또는 `commonProduct`: string (옵션)
- `ragStoreName`: string (옵션)
- `clarificationOption`: string (옵션)

> 주의: WEB 채널은 현재 “FDK처럼 commonProduct/sources를 필수로 강제”하지 않습니다(호환성 유지).

#### 응답(200)

- `ChatResponse` (멀티테넌트 chat 동작과 동일한 결과를 반환)

#### 에러(인증/서비스)

- 401: 필수 헤더 누락
  - 예: `{"detail":"X-Tenant-ID header is required"}`
- 403: API key 검증 실패
  - 예: `{"detail":"Invalid API key for the specified platform and tenant"}`
- 400: 지원하지 않는 platform 값 등
- 503: 채팅 서비스 미사용/미설정(멀티테넌트 handler가 없는 경우)

---

### 2) GET `/api/web/v1/chat/stream`

> `text/event-stream` (SSE) 스트리밍. 이벤트 포맷은 PR7까지의 레거시 포맷을 유지합니다.

#### 요청(Query params)

- `sessionId`: string (필수)
- `query`: string (필수)
- `sources`: string 또는 string[] (옵션)
- `product`: string (옵션)

#### 응답(200)

- `text/event-stream`

#### 에러(인증)

- POST `/chat`과 동일한 401/403/400 에러 계약을 사용합니다.

---

### 3) GET `/api/web/v1/tenant/info`

- 인증 헤더 필요(401/403 가능)
- 응답: 현재 테넌트 컨텍스트 요약

---

### 4) GET `/api/web/v1/health`

- 인증 헤더 **옵션** (`get_optional_tenant_context`)
- 응답에 `authenticated`/`tenant_id` 포함

## 구현/테스트 근거

- 구현: `app/api/routes/channel_web_v1.py`
- 인증 헤더 규칙: `app/middleware/tenant_auth.py`
- 관련 테스트: `tests/test_channel_bff_chat.py`

