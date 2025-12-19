# 레거시 관측 플레이북(수집/대시보드/알람)

> 목적: `/api/chat`, `/api/chat/stream`(레거시) 호출이 **온보딩 이외의 운영 트래픽**에서도 들어올 수 있으므로,
> 로그 기반으로 “누가/얼마나/어떻게” 쓰는지 빠르게 파악하고, 전환 의사결정(레거시 유지/감축/종료)을 가능하게 합니다.

## 1) 수집 대상 로그

레거시 관측 로그는 아래 패턴으로 찍힙니다.

- prefix: `legacy_request_json`
- payload: JSON 문자열(파싱 가능)

구현: `app/middleware/legacy_observability.py`

### JSON 필드(고정)

- `event`: `"legacy_request"`
- `request_id`: string
- `route`: `"/api/chat"` 또는 `"/api/chat/stream"`
- `method`: `"POST"` 또는 `"GET"`
- `status`: number
- `elapsed_ms`: number
- `has_tenant_headers`: boolean
- `tenant_id`: string | null
- `platform`: string | null
- `query_len`: number | null (stream에서만)

> 민감정보 주의: API key/쿼리 본문은 로깅하지 않습니다(길이만 기록).

## 2) “지금 당장” 확인(운영 서버 로그)

예시(로그 플랫폼 불문):

- 레거시 호출만 보기: `legacy_request_json`
- 스트림만 보기: `legacy_request_json` + `"/api/chat/stream"`
- 상태코드 4xx/5xx 보기: `legacy_request_json` + `"status":4` 또는 `"status":5`

## 3) 대시보드(추천 패널)

### 3.1 트래픽 볼륨

- 패널: `legacy_request count by route`
  - group by: `route`
  - filter: `event="legacy_request"`

### 3.2 레거시 사용 주체(테넌트 헤더 유무)

- 패널: `legacy_request count by has_tenant_headers`
  - 해석:
    - `true`: 멀티테넌트 인증 헤더가 붙은 호출(잠재적으로 `/api/web/v1` 또는 `/api/multitenant`로 이관 가능)
    - `false`: 알 수 없는 레거시 클라이언트(강제 전환/필수값 추가 금지)

### 3.3 에러율

- 패널: `legacy_request error rate`
  - numerator: `status >= 400`
  - denominator: `all legacy_request`

### 3.4 지연시간(레거시 UX)

- 패널: `legacy_request p50/p95 elapsed_ms by route`
  - group by: `route`
  - value: `elapsed_ms`

## 4) 알람(추천 조건)

- 레거시 5xx 증가: `status >= 500` 비율이 X분 평균 기준 임계치 초과
- 레거시 지연 증가: `/api/chat/stream`의 `elapsed_ms` p95가 임계치 초과
- 레거시 호출 급증: `legacy_request` count가 평소 대비 급증

## 5) 다음 단계(의사결정)

레거시 전환 논의는 아래가 확보된 후에만 진행합니다.

- `route`별 호출량 추이
- `has_tenant_headers` 비율
- (가능하면) `tenant_id/platform` 상위 N

전환 원칙/가드레일은 `docs/renewal/LEGACY_TRANSITION_PLAN.md`를 따릅니다.

## 6) Fly 운영: 외부 로그 플랫폼 연결

Fly 운영 환경에서 “대시보드/알람까지” 연결하려면, 아래 플레이북을 참고합니다.

- `docs/renewal/FLY_LOG_DRAIN_PLAYBOOK.md`
