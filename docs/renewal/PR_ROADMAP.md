# 리뉴얼 PR 로드맵 (진행현황 공유용)

> 목적: 여러 작업자가 동시에 작업하더라도 “한 PR = 한 목적” 원칙으로 충돌을 줄이고,
> 진행 현황을 이 문서 1곳에서 확인할 수 있게 합니다.

## 운영 규칙(요약)

- 모든 작업은 브랜치 + PR 단위로 진행합니다.
- PR 본문에는 반드시 아래를 포함합니다.
  - 변경 목적(1~2문장)
  - 변경 범위(파일 목록)
  - 테스트 증빙(`pytest -q` 결과)
  - 요구사항 충족 근거(파일 경로 + 라인 번호)
- Breaking change(기존 API/응답/SSE 포맷 변경)는 버전 업 없이 금지합니다.

## 상태 정의

- 대기: 아직 시작 전
- 진행: 브랜치 작업 중
- 리뷰: PR 열림/리뷰 중
- 머지: main 반영 완료
- 보류: 의존성/리스크로 중단

## PR 목록

| PR | 제목 | 상태 | 담당 | 브랜치 | PR 링크 | 비고/의존성 |
|---:|---|---|---|---|---|---|
| PR0-A | Analyzer `source` 제안 제거 | 머지 |  | `fix/pr0-tests-green` | https://github.com/wedosoft/agent-platform/pull/1 | 핵심: `app/agents/analyzer.py` |
| PR0-C | pytest 안정화(외부 LLM 호출 차단) | 머지 |  | `fix/pr0-tests-green` | https://github.com/wedosoft/agent-platform/pull/1 | 핵심: `tests/conftest.py` |
| PR0-B | 가드레일(문서+PR 템플릿) | 머지 |  | `chore/pr0-renewal-guardrails-main` | https://github.com/wedosoft/agent-platform/pull/2 | `docs/renewal/*`, `.github/pull_request_template.md` |
| PR0-D | 인수인계 문서(HANDOFF) | 머지 |  | `chore/pr0-handoff-doc-main` | https://github.com/wedosoft/agent-platform/pull/3 | `docs/renewal/HANDOFF.md` |
| PR1 | 관측성(request_id + 단계별 timing 로그) | 머지 |  | `chore/pr1-observability-main` | https://github.com/wedosoft/agent-platform/pull/4 | 기능 변화 없이 계측만 |
| PR2 | LLM Gateway 뼈대(동작 동일) | 머지 |  | `feat/pr2-llm-gateway-main` | https://github.com/wedosoft/agent-platform/pull/5 | LLM 호출 단일 진입점 |
| PR3 | Local-first + Cloud fallback(Feature flag) | 머지 |  | `feat/pr3-local-first-fallback` | https://github.com/wedosoft/agent-platform/pull/6 | 목적별 라우팅/timeout |
| PR4 | Assist/fieldsOnly에 적용 + 검증 | 머지 |  | `feat/pr4-assist-fields-only-verify` | https://github.com/wedosoft/agent-platform/pull/7 | SSE 포맷 유지 |
| PR5 | 채널 BFF 정돈(`/api/{channel}/v1`) | 머지 |  | `feat/pr5-channel-bff-chat` | https://github.com/wedosoft/agent-platform/pull/8 | 점진적 전환 |
| PR6 | Chat Core 유스케이스 분리(`app/services`) | 머지 |  | `feat/pr6-chat-usecase` | https://github.com/wedosoft/agent-platform/pull/11 | 채널/레거시/멀티테넌트 로직 단일화 |
| PR7 | Chat 스트리밍 유스케이스 통일 | 머지 |  | `feat/pr7-chat-stream-usecase` | https://github.com/wedosoft/agent-platform/pull/13 | SSE 포맷 유지, stream 로직 단일화 |
| PR8 | 채널 BFF 어댑터 도입(`fdk/web v1`) | 머지 |  | `feat/pr8-channel-bff-adapters` | https://github.com/wedosoft/agent-platform/pull/15 | 채널별 변환/권한 레이어 분리 |
| PR9 | FDK 채널 sources 필수 | 머지 |  | `feat/pr9-fdk-sources-required` | https://github.com/wedosoft/agent-platform/pull/16 | sources 누락 시 400 |
| PR10 | FDK sources allowlist 검증 | 진행 |  | `feat/pr10-fdk-sources-allowlist` |  | `docs/renewal/PR10.md` |

## 인수인계/상태 공유

- 현재 상황/머지 순서/검증 방법: `docs/renewal/HANDOFF.md`
