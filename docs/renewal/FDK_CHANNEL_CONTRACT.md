# FDK 채널 계약 (단일 참조 문서)

> 목적: FDK 채널 BFF(`/api/fdk/v1/*`)의 **입력/에러 계약을 고정**해서, 프론트/채널 구현 실수와 “암묵적 동작”을 줄입니다.
>
> 구현 스펙(단일 소스): `app/api/routes/channel_fdk_v1.py`
>
> OpenAPI 확인: 로컬 실행 후 `/docs` 또는 `/openapi.json`

## 엔드포인트

### 1) POST `/api/fdk/v1/chat`

#### 요청(JSON)

- `sessionId`: string (필수)
- `query`: string (필수)
- `commonProduct` 또는 `product`: string (필수)
- `sources`: string[] (필수)
- `ragStoreName`: string (옵션)
- `clarificationOption`: string (옵션)

#### 응답(200)

- `ChatResponse` (레거시 응답 호환 유지)

#### 에러(400)

아래 케이스는 모두 **400**이며, `detail`이 문자열이거나 객체(dict)일 수 있습니다(케이스별로 계약 고정).

- `sources` 누락: `{"detail":"FDK 채널에서는 sources가 필수입니다."}`
- `commonProduct/product` 누락: `{"detail":{"error":"MISSING_COMMON_PRODUCT", ...}}`
- `sources` allowlist 위반: `{"detail":{"error":"INVALID_SOURCES", ...}}`
- `sources` 조합 규칙 위반: `{"detail":{"error":"INVALID_SOURCES_COMBINATION", ...}}`

---

### 2) GET `/api/fdk/v1/chat/stream`

> `text/event-stream` (SSE) 스트리밍. 이벤트 포맷은 PR7까지의 레거시 포맷을 유지합니다.

#### 요청(Query params)

- `sessionId`: string (필수)
- `query`: string (필수)
- `sources`: string 또는 string[] (필수)
- `product` 또는 `commonProduct`: string (필수, 레거시 호환)
- `ragStoreName`: string (옵션)
- `clarificationOption`: string (옵션)

#### 응답(200)

- `text/event-stream`

#### 에러(400)

- POST `/chat`의 400 계약과 동일한 에러 코드를 사용합니다.

## sources 규칙

### 1) 필수

- `sources`가 없거나 빈 배열이면 400.

### 2) allowlist

- 논리 키: `tickets`, `articles`, `common`
- 또는 설정된 store name: `settings.gemini_store_*` (레거시 `gemini_common_store_name` 포함)

### 3) 조합 제한(PR11)

- **논리 키 조합**: `tickets/articles/common`만으로 구성된 조합은 허용
  - 단, `common` **단독은 금지**
- **store name 조합**: store name을 사용한다면 **1개만 허용**하며 다른 sources와 혼용 불가

## commonProduct 규칙(PR11)

- `commonProduct`(또는 `product`)는 필수이며, 누락/빈값이면 400 (`MISSING_COMMON_PRODUCT`).

## 구현/테스트 근거

- 구현: `app/api/routes/channel_fdk_v1.py`
- 테스트: `tests/test_fdk_sources_required.py`, `tests/test_channel_bff_chat.py`

