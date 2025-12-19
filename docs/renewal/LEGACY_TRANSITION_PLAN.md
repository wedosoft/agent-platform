# 레거시 전환 계획(운영 중 레거시 고려)

> 목적: `/api/chat*` 등 **레거시 엔드포인트가 일부 운영 중**인 상황에서,
> “깨지지 않는 전환(병행 운영)”을 위한 가드레일과 마이그레이션 방향을 고정합니다.
>
> 이 문서는 **온보딩 시스템 이외의 기타 운영 트래픽**(알 수 없는 클라이언트 포함)을 고려하여,
> 레거시 제거/강제 전환을 당장 하지 않는 것을 원칙으로 합니다.

## 1) 범위(Scope)

### 이 문서가 다루는 “레거시”

- 레거시 Chat(통합 엔드포인트)
  - POST `/api/chat`
  - GET `/api/chat/stream`

### 이 문서가 “레거시 전환” 대상으로 보지 않는 것

- 온보딩 시스템(API 자체가 별도 도메인/기능): `app/api/routes/onboarding.py`
- 관리/동기화/파이프라인 등 기능성 API: `/api/admin`, `/api/sync/*`, `/api/pipeline/*` 등

## 2) 현재 API 표면(정리)

### 2.1 신규 표준(채널 BFF)

- FDK 채널(계약 강함)
  - POST `/api/fdk/v1/chat`
  - GET `/api/fdk/v1/chat/stream`
  - 계약 문서: `docs/renewal/FDK_CHANNEL_CONTRACT.md`
- WEB 채널(멀티테넌트 인증)
  - POST `/api/web/v1/chat`
  - GET `/api/web/v1/chat/stream`
  - 계약 문서: `docs/renewal/WEB_CHANNEL_CONTRACT.md`

### 2.2 멀티테넌트(네임스페이스 분리된 운영 경로)

- POST `/api/multitenant/chat`
- GET `/api/multitenant/chat/stream`

### 2.3 레거시 Chat(운영 호환 유지 경로)

- POST `/api/chat`
- GET `/api/chat/stream`

레거시 Chat은 “하위호환을 위해 유지”하며, **채널별 입력 계약 강제는 채널 BFF(`/api/{channel}/v1`)에서만** 진행합니다.

## 3) 레거시 전환의 기본 원칙(가드레일)

### 3.1 깨지지 않게: 레거시 계약은 유지

- `/api/chat`, `/api/chat/stream`의 요청/응답/스트리밍(SSE) 포맷은 **breaking change 금지**입니다.
- 새로운 요구사항(필수값, allowlist, 조합 제한 등)은 **레거시가 아니라 채널 BFF에서만** 강제합니다.

### 3.2 운영 중 레거시를 “정확히 모르는 상태”를 전제로

- 온보딩 시스템 외에도 운영 트래픽이 존재할 수 있으므로,
  “어떤 클라이언트가 어떤 payload로 호출하는지” 확인 전까지는
  레거시 강제 전환/삭제/필수값 추가를 하지 않습니다.

### 3.3 점진 전환: 새 경로를 만들고, 레거시는 유지

- 신규 기능/정책은 `/api/{channel}/v1/...`로만 추가
- 레거시는 “동작 유지 + 마이그레이션 가이드 제공” 형태로만 정리

## 4) 마이그레이션 가이드(권장 매핑)

| 기존 호출 | 권장 신규 호출 | 비고 |
|---|---|---|
| `/api/chat` | `/api/fdk/v1/chat` | FDK 채널 입력 계약(예: sources/commonProduct) 필요 |
| `/api/chat/stream` | `/api/fdk/v1/chat/stream` | FDK 채널 계약 적용 |
| `/api/chat` (멀티테넌트 인증 헤더 동반) | `/api/web/v1/chat` 또는 `/api/multitenant/chat` | 채널(BFF) vs 내부 운영 경로 선택 |
| `/api/chat/stream` (멀티테넌트 인증 헤더 동반) | `/api/web/v1/chat/stream` 또는 `/api/multitenant/chat/stream` | 동일 |

> “어느 신규 경로로 옮길지” 판단 기준:
> - **클라이언트가 ‘채널(프론트)’이면** `/api/{channel}/v1/...`
> - **내부/플랫폼 통합 운영 경로이면** `/api/multitenant/...`

## 5) 레거시 제거/강제 전환을 위한 선행 조건(필수)

레거시를 “없애자” 논의는 아래 조건을 **충족한 뒤**에만 가능합니다.

1) **트래픽 관측**
   - 최소 N주(예: 2~4주) 동안 `/api/chat*` 호출을 관측하고,
     - 호출 주체(헤더/도메인/UA)
     - 요청 payload 패턴
     - 에러율/응답시간
     를 파악
2) **대체 경로 이행률 확인**
   - 대체 경로(`/api/fdk/v1/*`, `/api/web/v1/*`, `/api/multitenant/*`)로의 이행률이 충분히 높을 것
3) **명시적 공지/유예**
   - Sunset(종료) 일정은 문서/공지로 명시하고, 유예 기간을 둘 것

> 현재는 “운영 중 레거시 존재(온보딩 이외 기타 포함)”가 전제이므로, 본 문서는 **Sunset 날짜를 정하지 않습니다.**

## 6) 다음 PR 후보(선택)

운영 가시성을 높이기 위해, 아래는 “문서 이후”에 별도 PR로 진행하는 것을 권장합니다.

- 레거시 호출 관측(로그/메트릭)
  - `/api/chat*` 호출 시 `route`, `channel(legacy)`, `has_tenant_headers` 같은 태그를 남기기
  - 단, 응답/동작에는 영향 없게(관측 전용)
  - 구현 예: `app/middleware/legacy_observability.py`
  - 운영 플레이북: `docs/renewal/LEGACY_OBSERVABILITY_PLAYBOOK.md`
