# 리뉴얼 인수인계(Handoff) 노트

> 이 문서는 “다음 작업자가 저장소만 보고” 바로 이어서 작업할 수 있도록,
> 현재까지의 진행상황/브랜치/검증 방법/머지 순서를 한 곳에 정리합니다.
>
> 기준일: 2025-12-17

## 0) 빠른 시작(다음 작업자용)

```bash
git fetch origin
git branch --all --sort=-committerdate | head -n 30
./venv/bin/python -m pytest -q
```

## 1) 진행 원칙(고정)

- 메인 직접 작업 금지: 브랜치 + PR 단위로만 진행
- 한 PR = 한 목적(비관련 변경 금지)
- 버전 업 없이 breaking change 금지(기존 API/응답/SSE 포맷 유지)
- 테스트에서 외부 네트워크 호출(LLM/RAG/플랫폼) 차단(override/mock 필수)
- PR 본문에 “요구사항 충족 근거(파일/라인)” + “테스트 증빙” 포함

## 2) 현재 브랜치/커밋 상태(원격 기준)

| 구분 | 브랜치 | HEAD(Short SHA) | 비고 |
|---|---|---:|---|
| PR0-B | `origin/chore/pr0-renewal-guardrails` | `d988e27` | 문서/가드레일/PR 템플릿 |
| PR0-A | `origin/fix/pr0-filter-source-proposals` | `ea6bd31` | Analyzer에서 `source` 제안 제거 |
| PR0-C | `origin/chore/pr0c-stabilize-pytest` | `54ab536` | pytest 안정화(외부 LLM 호출 차단) |
| PR1 | `origin/chore/pr1-observability-request-id` | `d47f5b4` | request_id + gemini timing 로그 |
| PR2 | `origin/feat/pr2-llm-gateway` | `11e4cfb` | LLM Gateway 뼈대 + 테스트 |

원격 HEAD 확인 명령:

```bash
git ls-remote --heads origin \
  chore/pr0-renewal-guardrails \
  fix/pr0-filter-source-proposals \
  chore/pr0c-stabilize-pytest \
  chore/pr1-observability-request-id \
  feat/pr2-llm-gateway
```

## 3) 주요 변경 포인트(근거/재현 가능한 방식)

### PR0-A: Analyzer에서 `source` 필드 제안 제거

- 목적: UI/테스트/계약에서 “source” 필드 제안이 나오지 않도록 강제
- 근거 확인:

```bash
git show ea6bd31:app/agents/analyzer.py | nl -ba | sed -n '1,120p'
# 핵심 라인: source proposal drop (예: 34~44)
```

### PR0-C: 테스트에서 외부 LLM 호출 차단(플래키 제거)

- 배경(이전 문제): 일부 테스트가 실제 LLM 네트워크 호출을 타면서 teardown 시점에 `Event loop is closed`로 플래키 실패
- 해결: 테스트 기본값으로 `LLMAdapter` 호출을 stub 처리 + `TestClient` 종료 보장
- 근거 확인:

```bash
git show 54ab536:tests/conftest.py | nl -ba | sed -n '1,220p'
# 핵심 라인: stub_llm_calls fixture (예: 21~54), TestClient with (예: 141~145)
```

검증(최소 재현 조합):

```bash
git checkout chore/pr0c-stabilize-pytest
./venv/bin/python -m pytest -q tests/test_assist_api.py tests/test_multitenant_auth.py
./venv/bin/python -m pytest -q
```

### PR1: request_id + gemini search timing 로그

근거 확인:

```bash
git show d47f5b4:app/services/common_chat_handler.py | nl -ba | sed -n '220,320p'
git show d47f5b4:app/services/multitenant_chat_handler.py | nl -ba | sed -n '120,210p'

git show 020ae9b:app/middleware/request_id.py | nl -ba | sed -n '1,120p'
git show 020ae9b:app/main.py | nl -ba | sed -n '1,130p'
```

### PR2: LLM Gateway 뼈대

근거 확인:

```bash
git show 11e4cfb:app/services/llm_gateway.py | nl -ba | sed -n '1,240p'
git show 11e4cfb:app/services/llm_adapter.py | nl -ba | sed -n '260,360p'
git show 11e4cfb:tests/test_llm_gateway.py | nl -ba | sed -n '1,220p'
```

## 4) 권장 머지 순서(의존성/리스크 최소화)

1. PR0-B → main (문서/템플릿/가드레일 먼저)
2. PR0-A → main
3. PR0-C → main (PR0-A 반영 후)
4. PR1/PR2는 main 최신으로 rebase/merge 후 `./venv/bin/python -m pytest -q` 통과 확인하고 머지

## 5) 다음 작업자가 “상태 공유”하는 방법(수동 전달 최소화)

- 단일 진실 소스: `docs/renewal/PR_ROADMAP.md`에 PR 링크/상태를 갱신
- PR 본문에 “요구사항 체크리스트 + 근거(파일/라인) + pytest 증빙”을 남겨서, PR 자체가 인수인계 문서가 되게 유지

