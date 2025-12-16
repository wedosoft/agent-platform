# 멀티 프론트(채널) 확장 대비 백엔드 설계 메모 (Agent Platform)

> 목적: Freshdesk FDK 앱을 시작으로 Zendesk/사내·외부 웹/모바일 등 프론트(채널)가 계속 늘어나는 상황에서, 백엔드를 “단일 백본”으로 유지하면서도 확장/운영 가능한 구조와 정책을 합의하기 위한 핸드오프 문서.
>
> 작성 시점: 2025-12-16
>
> 리포 컨텍스트:
> - `project-a`: Freshdesk App(FDK) 프론트 중심
> - `agent-platform`: 공용 백엔드(본 문서의 대상)

---

## 0. TL;DR (합의된 큰 방향)

- **모듈러 모놀리스(Core) + 채널별 BFF(Interfaces) + 계약/버전/디프리케이션 정책 + 테넌시/관측/회복력 표준화**가 기본 전략.
- “처음부터 마이크로서비스 분리”는 지양하고, **경계(모듈/계약)를 먼저 단단히 만든 후 필요 시 점진 분리**한다.
- 멀티 프론트 확장 시 반드시 정책으로 못 박아야 하는 2가지:
  1) **테넌트/권한 판정에 클라이언트 헤더(`X-Tenant-ID` 등)를 신뢰하지 않는다.** 서버가 인증 크리덴셜로부터 `TenantContext`를 계산한다.
  2) **BFF는 얇게 유지**(변환/오케스트레이션/캐싱/타임박스)하고, 도메인 규칙·상태 전이·권한 정책의 “실체”는 Core 유즈케이스에서만 수행한다.

---

## 1. 배경/요구사항

### 채널 확장 범위(예상)
- 확정/우선: **Freshdesk(FDK)**
- 확장 가능: **Zendesk**, 사내 웹, 외부 고객용 웹 위젯, 모바일
- API는 “파트너 공개” 목적이 아니라 **사내/자사 프론트용**(internal/first-party) 성격

### 인증 수단(불확실)
- 채널에 따라 설치 단계 secret 저장/Google 로그인(JWT)/API key 형태 혼재 가능
- 따라서 **인증 전략은 ‘플러그 가능’해야 함**

### 데이터/스토리지
- SoR(System of Record): **Supabase Postgres**
- RAG Store: **Google File Search(=Gemini File Search)** 우선
- 필요 시 벡터 DB(Qdrant) 도입 가능성 있음

### 성능/시간 제약
- FDK serverless timeout: **15초(하드 리밋)**
- 실제 UX 목표: **최대 5초를 넘기면 안됨**
  - 따라서: **타임박스 + 부분 결과(스트리밍) + 폴백(direct)** 가 표준 패턴이 되어야 함

---

## 2. 현재 코드/구조 요약 (agent-platform)

### 주요 디렉터리
- `app/api/routes/*`: 라우트(채널별/기능별 API가 한 앱에 혼재)
- `app/services/*`: 서비스(유즈케이스/인프라 어댑터가 혼재)
- `app/agents/*`: LangGraph 기반 에이전트(검색/분석/합성)
- `app/middleware/*`: 멀티테넌트 인증 등
- `supabase/migrations/*`: Supabase 스키마/마이그레이션

### 관찰된 이슈/부채(설계 관점)
- **Interfaces 경계가 느슨함**: FDK/온보딩/멀티테넌트/agent chat 등이 `/api` 아래 혼재
- **워크플로우 중복**: LangGraph(agents)와 FDK 전용 assist 로직이 비슷한 역할을 중복 구현
- **검색 경로 비활성화 가능성**: `app/agents/retriever.py`에 “Gemini Search 임시 스킵” 로직 존재(성능 이슈 대응)
- **저장소 이중화**: 일부는 Redis/인메모리, 일부는 Supabase(영속/캐시)로 혼재

---

## 3. 목표 아키텍처(권장)

### 3.1 레이어(역할/책임)

1) **Interfaces(BFF)**: 채널별 API 계약·DTO, 인증 진입점, 요청/응답 변환, 오케스트레이션, 단기 캐시, 타임박스/폴백
2) **Application(Use cases)**: “분석하기/승인하기/동기화/채팅” 같은 유즈케이스; 정책 적용; 트랜잭션 경계
3) **Domain**: 도메인 규칙/상태 전이/검증(순수 로직)
4) **Infrastructure**: Freshdesk/Zendesk/Gemini/Supabase/Redis/Qdrant/Pipeline 등 외부 연동 어댑터

> 운영 안정성을 위해 “규칙·정책·권한의 실체”는 반드시 Application/Domain 레이어에만 두고, BFF는 thin layer로 유지한다.

### 3.2 API 네임스페이스(채널+버전)

- 신규 표준: `/api/{channel}/v{n}/...`
  - 예: `/api/fdk/v1/*`, `/api/zendesk/v1/*`, `/api/web/v1/*`, `/api/mobile/v1/*`, `/api/admin/v1/*`
- 기존 경로(`/api/assist`, `/api/onboarding`, `/api/multitenant` 등)는
  - 단기: 호환 유지
  - 중기: 새 경로로 병행 제공
  - 장기: **Deprecation+Sunset(예: 90일)** 후 제거

### 3.3 계약/버전/디프리케이션 정책

- BFF별 OpenAPI/JSON Schema를 버전 관리
- Breaking change는 새 `/v{n}`만 허용
- 디프리케이션은 **표준 헤더로 공지**:
  - `Deprecation: true`
  - `Sunset: <date>`
- (권장) 채널별 CDC(Consumer-driven contract) 테스트로 회귀 차단

---

## 4. 멀티테넌트/인증 정책(필수 합의 사항)

### 4.1 핵심 원칙

- `X-Tenant-ID`, `X-Platform` 등은 **로깅/디버깅 힌트**로만 사용
- **테넌트/권한 판정은 “서버가 검증한 크리덴셜”에서만** 파생
  - (예) Bearer JWT, HMAC 서명, 설치 시 발급된 client_secret 기반 토큰, service token 등

### 4.2 권장 인증 전략(채널별)

- **웹/모바일**: Supabase JWT(`Authorization: Bearer`) → user→tenant 매핑으로 `TenantContext` 구성
- **Freshdesk/Zendesk 앱**:
  - 설치/관리 단계에서 연동 자격(도메인, API key 등)을 등록/검증
  - 런타임 호출은 **백엔드 발급 client_secret 기반 HMAC 서명 또는 단기 JWT**로 호출
  - 목적: 플랫폼 API key를 매 요청에 싣지 않게(보안/성능/레이트리밋)
- **내부 API(자사용)**: service token(관리자 키와 분리) + scope 최소화

---

## 5. 성능(5초 UX) 표준 패턴

### 5.1 타임박스(권장)

- “사용자 요청”은 5초 내에 의미 있는 응답 제공
- RAG/외부호출은 타임박스 내 시도하고, 실패 시 즉시 폴백:
  - 예: `retrieve <= 1500~2000ms` → 실패/지연 시 direct 모드로 전환

### 5.2 스트리밍(SSE) 표준화

- FDK(15초 리밋) 환경에서 **부분 결과를 빠르게 표시**하는 것이 UX 핵심
- 표준 이벤트 예:
  - `router_decision` → `retriever_start` → `analysis_complete` → `draft_ready` → `complete` (+ `error`)

---

## 6. 회복탄력성/관측성

### 회복탄력성
- 외부 연동(Freshdesk/Zendesk/Gemini/Supabase/Pipeline)에 공통 적용:
  - `timeout`, `retry(멱등만)`, `circuit breaker`, `fallback`

### 관측성(OpenTelemetry)
- traces/metrics/logs를 표준으로 수집
- 모든 요청에 correlation id(예: `X-Request-Id`) 부여
- 로그/트레이스 태그 표준: `tenant_id`, `channel`, `version`, `route`, `mode(direct|rag|fallback)`

---

## 7. 테넌트 테이블 통합(현재 스키마 기반)

> 사용자 요구: “현재 테이블 구조를 고려해서 테넌트 관리 효율화. 현재 테넌트는 FDK 사용자를 위한 멀티테넌트.”

### 7.1 현재 관찰(스크린샷 + 마이그레이션)

- 스키마에 `tenants`, `tenant_orgs`가 동시에 존재(이중화)
- `tenant_platforms` 존재(플랫폼별 설정 테이블)
- `tenant_ticket_metadata`, `tenant_article_metadata` 존재(필터링/메타데이터)
- `tenant_ticket_fields` 존재(티켓 필드 캐시)

관련 마이그레이션:
- `supabase/migrations/20251126000001_multitenant_tables.sql` (tenants/tenant_platforms/ticket_metadata/article_metadata + RLS + RPC)
- `supabase/migrations/20251127000001_create_new_naming_tables.sql` (tenant_orgs + tenant_ticket_metadata/tenant_article_metadata 등 “신규 네이밍” 테이블)
- `supabase/migrations/20251213000000_tenant_ticket_fields_cache.sql` (`tenant_ticket_fields`가 `tenants(id)`를 참조)

### 7.2 통합 원칙(권장)

- **단일 SoT(Source of Truth) 테이블을 하나로 확정**해야 함.
- 추천: **`tenants`를 SoT로 유지**하고, `tenant_orgs`는 필요 시 VIEW로 대체.
  - 이유: 이미 RPC(`get_tenant_by_domain`) 및 `tenant_ticket_fields` 캐시가 `tenants` 기준으로 동작(코드도 그 전제)

### 7.3 통합안(최소 변경/최대 효율)

1) **조직 테이블 단일화**
   - SoT: `tenants`
   - 네이밍 컨벤션이 필요하면: `CREATE VIEW tenant_orgs AS SELECT * FROM tenants;` (또는 반대 방향을 택할 경우, 모든 FK/코드가 그 방향으로 정리되어야 함)

2) **플랫폼 연동/채널 인증을 `tenant_platforms`로 흡수**
   - 별도 `tenant_integrations`, `api_clients`를 “지금 당장” 만들기보다,
   - `tenant_platforms`에 필요한 컬럼을 확장해 통합 관리:
     - (연동) `domain`, `enabled`, `custom_store`, `stores_jsonb`(선택)
     - (호출 인증) `auth_mode`, `client_id`, `client_secret_hash`(또는 공개키), `last_rotated_at`
     - (플랫폼 자격증명) `credentials_enc`(암호화 JSON) 또는 `secret_ref`(Vault 사용 시)

3) **메타데이터 테이블 FK 일관화**
   - `tenant_ticket_metadata`, `tenant_article_metadata`, `tenant_ticket_fields` 모두 `tenants(id)`를 참조하도록 통일

4) **RLS 정리**
   - tenant 관련 테이블은 `UNRESTRICTED` 상태가 없도록 정리(최소 `service_role` full access + tenant isolation)

### 7.4 추가 논의가 필요한 결정 포인트(필수)

- (D1) SoT는 `tenants` vs `tenant_orgs` 중 무엇인가? (권장: `tenants`)
- (D2) 플랫폼 자격증명 저장 방식
  - Supabase Vault/pgcrypto로 DB 암호화 저장 vs 외부 Secret Manager(Vault 등) 참조
- (D3) `tenant_platforms`에서 “호출 인증(client secret)”까지 같이 들고 갈지,
  - 또는 platform과 무관한 `tenant_api_clients`(1 tenant - N clients)로 분리할지
  - 권장: 지금은 `tenant_platforms` 확장으로 시작, “같은 platform에 여러 클라이언트(웹/모바일)가 늘어나면” 분리

---

## 8. 다음 작업 제안(우선순위)

### 8.1 스키마/테넌시 정리(최우선)
- (A) `tenants`/`tenant_orgs` SoT 결정 및 FK 통일 마이그레이션 설계
- (B) `tenant_platforms` 확장(연동+호출 인증+자격증명 저장 구조)
- (C) tenant 관련 테이블 RLS 정책 표준화

### 8.2 API 경계/버전 정리
- `/api/{channel}/v1` 네임스페이스 신설 + 기존 엔드포인트 호환/디프리케이션 정책 적용

### 8.3 성능(5초) 체계화
- Retriever 타임박스/폴백 표준화(“FDK UX 5초”) + SSE 이벤트 표준

### 8.4 관측성/Otel
- correlation id, tenant/channel/version 태그 표준, 주요 외부 호출 span 정리

### 8.5 계약 테스트(CDC)
- 채널별 소비자 계약 기반 테스트 도입(멀티 프론트 확장 시 QA 비용 폭증 방지)

---

## 9. 참고(현재 코드/문서 포인터)

- API Router: `app/api/router.py`
- FDK Assist(주요): `app/api/routes/assist.py`
- 멀티테넌트 인증: `app/middleware/tenant_auth.py`, `app/api/routes/multitenant.py`
- 테넌트 레지스트리(구형): `app/services/tenant_registry.py` (env JSON 기반)
- Supabase ticket fields 캐시: `app/services/tenant_ticket_fields_cache.py`
- Multitenant 테이블: `supabase/migrations/20251126000001_multitenant_tables.sql`
- 신규 네이밍 테이블: `supabase/migrations/20251127000001_create_new_naming_tables.sql`

