# Fly 로그 드레인/대시보드 연결 플레이북

> 목적: Fly에서 운영 중인 앱의 로그를 “외부 로그 플랫폼(검색/대시보드/알람)”으로 보내서,
> 레거시(`/api/chat*`) 포함 실제 운영 트래픽을 안정적으로 관측합니다.
>
> 참고: 현재 개발 환경의 `flyctl v0.3.232` 기준으로 `flyctl log-drains ...` 같은 CLI 명령은 제공되지 않습니다.
> 따라서 아래 2가지 방식 중 하나를 선택합니다.

## 방식 A) Fly Dashboard에서 Log Drain 설정(가장 간단)

1) Fly Dashboard에서 대상 앱(예: `agent-platform`) 선택
2) Log drains(또는 Observability 설정)에서 외부 로그 수집 엔드포인트 추가
3) 외부 로그 플랫폼에서:
   - 인덱스/소스명(예: `fly.agent-platform`)
   - 파서(JSON / key-value)
   - 알람 룰(5xx, 지연, 트래픽 급증)
   을 구성

> 장점: 가장 빠르고 간단\n
> 단점: 설정이 코드로 남지 않음(운영 지식이 UI에 묶임)

## 방식 B) Fly Log Shipper(별도 앱)로 로그 전달(추천: 재현 가능/확장 가능)

> 아이디어: “로그를 받아서(구독) → 외부로 전달”하는 전용 Fly 앱을 하나 띄웁니다.
> 이 앱이 `agent-platform`의 로그 subject만 골라서 외부 플랫폼으로 보냅니다.

### B-1) 준비물(결정해야 할 것)

- 외부 로그 플랫폼 선택
  - 예: Grafana Loki(자체/클라우드), Datadog, Better Stack, Elastic 등
- 외부 플랫폼 수집 엔드포인트/토큰
- Fly 조직 slug(예: `wedosoft`)

### B-2) Log Shipper 앱 생성(예시)

아래는 “전용 shipper 앱”을 하나 만들고 배포하는 예시입니다(이 레포에는 코드를 추가하지 않고, 운영에서 실행).

```bash
# 1) 전용 디렉토리에서 새 Fly 앱 생성(별도 repo/폴더여도 됨)
mkdir -p fly-log-shipper && cd fly-log-shipper

# 2) Log Shipper 이미지로 launch (deploy는 나중에)
flyctl launch --no-deploy --image ghcr.io/superfly/fly-log-shipper:latest
```

### B-3) 권한(토큰)과 구독(Subject) 설정

```bash
# 조직/앱 슬러그는 환경에 맞게 변경
export FLY_ORG_SLUG="<your-org-slug>"
export SOURCE_APP_SLUG="agent-platform"

# 로그를 “읽기 전용”으로 가져오기 위한 토큰(조직 기준)
flyctl tokens create readonly "$FLY_ORG_SLUG"
# 출력된 토큰을 아래 ACCESS_TOKEN에 사용

# 특정 앱 로그만 구독하도록 subject 지정
# (예: agent-platform의 로그만)
export LOG_SUBJECT="logs.${SOURCE_APP_SLUG}.>"

# shipper 앱에 시크릿 설정
flyctl secrets set \
  ORG="$FLY_ORG_SLUG" \
  ACCESS_TOKEN="<readonly-token>" \
  SUBJECT="$LOG_SUBJECT"
```

> 보안: `ACCESS_TOKEN`은 시크릿으로만 관리하고, 절대 코드/문서에 하드코딩하지 않습니다.

### B-4) 외부 로그 플랫폼으로 보내기(예시: Loki)

Log Shipper는 내부적으로 Vector 설정을 사용하므로, 선택한 플랫폼에 맞는 sink 설정이 필요합니다.
아래는 “Loki로 보내는” 형태의 예시(플레이스홀더)입니다.

```toml
# vector.toml (예시)
[sources.fly_logs]
type = "fly_logs"
org = "${ORG}"
access_token = "${ACCESS_TOKEN}"
subject = "${SUBJECT}"

[sinks.loki]
type = "loki"
inputs = ["fly_logs"]
endpoint = "${LOKI_ENDPOINT}"
labels.app = "agent-platform"
labels.env = "${ENVIRONMENT}"
encoding.codec = "json"
```

그 다음 shipper 앱에 환경 변수/시크릿을 추가하고, Vector 설정을 shipper 앱에 주입한 뒤 배포합니다.

```bash
flyctl secrets set \
  LOKI_ENDPOINT="<https://...>" \
  ENVIRONMENT="<prod|staging>"

# 배포(구체적인 config 주입 방식은 운영 환경 선택에 따라 다르므로, 팀 표준으로 고정 필요)
flyctl deploy
```

### B-5) 대시보드/알람(최소 권장)

`docs/renewal/LEGACY_OBSERVABILITY_PLAYBOOK.md` 기준으로 아래를 필수로 구성합니다.

- `legacy_request` 트래픽(분당) / route별
- `legacy_request` 에러율(4xx/5xx)
- `elapsed_ms` p95(route별)
- `has_tenant_headers` 비율 추이(이행 가능성 판단)

## 운영 체크리스트(권장)

- [ ] 외부 플랫폼에서 `legacy_request_json` 로그가 수집되는지 확인
- [ ] JSON 파싱 규칙 설정(필드 추출)
- [ ] 알람(5xx, p95 지연, 트래픽 급증) 1차 적용
- [ ] 2~4주 관측 후 레거시 전환 판단(LEGACY_TRANSITION_PLAN 준수)

