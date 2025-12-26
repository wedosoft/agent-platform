# Copilot 지침: 리팩터링 PR Plan (3 PR)

## 공통 규칙(모든 PR에 적용)

* 목표: **Freshdesk 티켓 “답장”이 아니라 “분석 리포트”** 생성
* 입력: `ticket_normalized_v1` JSON만 허용(검증 실패 시 400)
* 출력: `ticket_analysis_v1` JSON만 “정답”(자연어 출력 금지)
* API: `POST /api/tickets/{ticket_id}/analyze` (채팅 API 아님)
* 결과에는 반드시: `analysis_id`, `ticket_id`, `status`, `gate`, `analysis`, `meta`
* `gate ∈ {CONFIRM, EDIT, DECIDE, TEACH}` 는 **상담원 UI 모드 값**
* 교훈(lessons)은 **quarantine 저장**이 기본(조직 정책 승격은 이번 3PR 범위 제외)
* 테스트 없는 변경 금지(최소 e2e 1개 + 에러 2개)

---

## PR1 — Schemas + Validator + Analyze API Skeleton

### 목적

* “스키마가 곧 법”을 코드로 강제
* 엔드포인트/응답 계약을 고정해서 프론트와 병렬 개발 가능하게 만들기

### 작업 범위(Backend: agent-platform)

1. `app/schemas/`

   * `ticket_normalized_v1.json`
   * `ticket_analysis_v1.json`
2. `app/utils/schema_validation.py` (또는 유사 위치)

   * `validate_or_raise(schema_name: str, obj: dict) -> None`
   * JSON parse 실패/검증 실패 시 예외 타입 분리
3. `POST /api/tickets/{ticket_id}/analyze`

   * 라우터는 얇게: 입력 검증 → Orchestrator 호출(일단 stub) → 응답 래핑
   * Orchestrator가 아직 없으면 임시로 더미 `analysis`를 생성하되, **출력은 반드시 ticket_analysis_v1 스키마를 만족**
4. 에러 응답 규격 고정

   * 400: `INVALID_INPUT_SCHEMA`
   * 500: `ANALYSIS_FAILED`

### DoD (완료 조건)

* (1) 샘플 `ticket_normalized_v1`로 호출 시 200 OK
* (2) 응답 `analysis`가 `ticket_analysis_v1` 스키마 검증 통과
* (3) 잘못된 입력(필수필드 누락) → 400 + `INVALID_INPUT_SCHEMA`
* (4) 단위 테스트 또는 e2e 테스트 최소 1개 포함

---

## PR2 — Orchestrator + Prompt Registry v1 + Persist (Runs/Analyses)

### 목적

* 실제 분석 파이프라인을 붙이고, “재현/비교/학습”이 가능하도록 저장까지 끝낸다

### 작업 범위(Backend: agent-platform)

#### A) Prompt Registry v1

1. `app/prompts/registry/ticket_analysis_cot_v1.yaml` 추가

   * purpose, model_defaults, input_schema, output_schema, template, known_failure_modes, eval_checks 포함
2. `app/prompts/loader.py`

   * `load_prompt(name: str) -> PromptSpec`

#### B) Orchestrator

1. `app/services/orchestrator/ticket_analysis_orchestrator.py`

   * 함수 시그니처 고정:

     * `run_ticket_analysis(input: dict, options: dict) -> (analysis: dict, gate: str, meta: dict)`
   * 파이프라인 순서 고정:

     1. Validate input(`ticket_normalized_v1`)
     2. Build prompt from registry
     3. Call LLM
     4. Parse JSON (JSON 외 텍스트 있으면 실패 처리 또는 repair)
     5. Validate output(`ticket_analysis_v1`)
     6. Compute gate(불확실성/점수 기반 최소 버전: confidence, open_questions, risk_tags로 결정)
     7. Persist (run + analysis)
2. JSON Repair (최소)

   * “JSON만 반환” 위반 시: 가장 단순한 repair(코드블록 제거/앞뒤 텍스트 제거) 1회 시도 후 실패

#### C) Persistence(최소 DB 모델)

* `analysis_runs` 테이블(또는 supabase 테이블)

  * analysis_id, ticket_id, prompt_version, model, params, status, latency_ms, cost, created_at
* `ticket_analyses` 테이블

  * analysis_id(FK), analysis_json, confidence, issue_type, root_cause, created_at
* 저장은 “완전한 분석 JSON”을 그대로 넣는다(후처리로 필드 분리 가능)

#### D) Endpoint 연결

* PR1의 analyze endpoint가 Orchestrator를 실제로 호출하도록 변경

### DoD

* (1) 실제 LLM 호출로 `ticket_analysis_v1` 생성
* (2) `analysis_runs`와 `ticket_analyses`에 저장됨
* (3) 응답에 `analysis_id`, `gate`, `analysis`, `meta` 포함
* (4) 실패 시나리오 2개 테스트:

  * LLM이 JSON 아닌 텍스트 섞어 출력 → repair 1회 후 실패면 500
  * output 스키마 불일치 → 500(또는 422 정책을 쓰면 PR3에서 프론트가 처리 가능하게 일관되게)
* (5) 로그에는 남겨도 되지만, **API 응답은 JSON만**

---

## PR3 — project-a(Freshdesk App) Analyze/Evidence/Teach/History UI + API 연동

### 목적

* 답장 중심 UI를 금지하고, “분석 콘솔”을 실제 상담원 작업 흐름으로 만든다

### 작업 범위(Frontend: project-a)

#### A) UI 탭(최소 4개)

1. **Analyze**

   * 분석 실행 버튼 → `POST /api/tickets/{ticket_id}/analyze`
   * 결과 렌더:

     * narrative.summary/timeline
     * root_cause
     * resolution[]
     * confidence
     * gate 표시
2. **Evidence**

   * `analysis.evidence[]` 목록/필터(type별)
3. **Teach**

   * 교훈 입력 폼(스키마 고정):

     * mistake_pattern
     * wrong_assumption
     * corrective_heuristic
     * automation_possible
   * 제출 → `POST /api/analyses/{analysis_id}/teach` (백엔드가 아직 없으면 PR3에서 함께 추가하거나, 임시로 저장 API만 만들어도 됨)
4. **History**

   * 동일 ticket_id의 analysis_runs 목록 조회
   * 클릭 시 과거 analysis 로드/비교

#### B) UI 상태 머신(필수)

* `IDLE` → `RUNNING` → `COMPLETED`
* `NEEDS_REVIEW` (gate=DECIDE/TEACH 일 때 뱃지/가이드)
* `ERROR`

#### C) “답장”은 옵션 기능으로만

* 기본 CTA는 “티켓 분석”
* 답장 초안 버튼이 있더라도 “부가 액션”으로만 두고, PR3 범위에서는 구현하지 않아도 됨(오히려 금지 권장)

### DoD

* (1) Freshdesk 티켓 화면에서 Analyze 실행 → 결과 렌더
* (2) gate 값에 따라 UI 안내가 바뀜(DECIDE/TEACH 표시)
* (3) Evidence 탭에서 evidence 리스트가 보임
* (4) History에서 최소 1개 과거 run을 불러올 수 있음(백엔드 엔드포인트 필요)
* (5) Teach 폼 제출이 성공 응답을 받음(저장까지 또는 임시 저장이라도 end-to-end 동작)

---

# 3 PR 이후(명시적으로 “범위 밖”으로 남기는 것)

* 유사 티켓/KB 하이브리드 검색(Retrieval 고도화)
* Policy/Org Memory 승격 워크플로우(PR 승인/권한)
* 고급 평가(정교한 score_breakdown, 위험 태그 자동 분류)
* SSE/Webhook 기반 비동기 처리(대형 티켓 대응)

---
