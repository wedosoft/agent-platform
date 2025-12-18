아래 내용은 **코덱스/코파일럿이 “바로” 작업을 시작할 수 있게** 만드는 실전 지침서입니다. 요청하신 대로 **1번부터 순서대로** 드리겠습니다. (그대로 `docs/renewal/`에 복사해 넣고 시작하셔도 됩니다.)

---

# 1) AI용 Core Design Contract (리뉴얼 작업의 “불변 규칙”)

> 문서 목적: **코덱스/코파일럿이 “큰 그림”을 유지하면서도, PR을 쪼개서 안전하게 리뉴얼**하도록 강제하는 계약서입니다.
> 이 계약을 어기면 “빠르게 만들었지만 결국 다시 뜯어고치는” 상황이 발생합니다.

## 1.1. 이 리포의 목표(What / Why)

* 이 저장소는 **다수의 프론트(채널/플랫폼)를 지원하는 통합 백엔드**입니다.
* 현재 가장 큰 병목은 **LLM 호출 지연(네트워크 + 생성 시간 + 토큰/프롬프트 비대화)**이고, 프론트 UX를 깨고 있습니다.
* 목표는 “LLM을 없애기”가 아니라, **Local/오픈소스/온디바이스 모델을 기본 경로로 두고**, 품질/정합성/복잡도 높은 케이스에서만 **Cloud LLM로 폴백**하는 구조입니다.

**핵심 KPI (권장)**

* 사용자 체감: “첫 이벤트(스트리밍) < 1s”, “첫 유의미한 텍스트 < 2~3s”
* 동기 응답: 기본 타임박스 5s, 절대상한(프론트/플랫폼 제약) 15s
* LLM 비용/지연: “LLM 호출 횟수, 평균 ms, P95 ms”를 기능별(purpose)로 측정

## 1.2. 용어 정의(팀/AI 공통 언어)

* **Channel / Front**: Freshdesk, Zendesk, Web, Admin 등 호출 주체
* **BFF(채널 BFF)**: 채널별 요구를 반영하는 얇은 API 계층(입출력/변환/권한/요청 조립)
* **Core(Application/Domain)**: 비즈니스 로직(검색 → 추론 → 결과 조립). 채널 중립적
* **Infra(Service/Adapter)**: 외부 의존성(Supabase, Freshdesk, Gemini, LLM Provider 등). “얇게” 유지 
* **LLM Gateway**: 모든 LLM 호출이 통과하는 단일 진입점(라우팅, 타임아웃, 폴백, 로깅, 캐시)

## 1.3. 아키텍처 원칙(Non‑negotiables)

### A) “서비스는 얇게, 로직은 Core로”

* `app/services`는 외부 I/O 어댑터 성격으로 얇게 유지하고, 테스트 가능한 순수 로직은 분리합니다. 
* 리뉴얼 과정에서 **핸들러/라우터에 로직을 쌓지 않습니다.**
* 새 로직은 가능하면 `app/application/` (혹은 `app/core/usecases/`)에 모읍니다.

### B) API 경로/버전 규칙

* 기존 원칙: 라우트는 `settings.api_prefix`(기본 `/api`) 하위에서 일관되게 유지 , 
* 리뉴얼 목표: 신규 기능은 **`/api/{channel}/v1/...` 형태로 확장**(기존 `/api/chat`, `/api/assist` 등은 당장 깨지지 않게 유지/별칭).
* **Breaking change 금지**: 기존 응답 필드/스트리밍 이벤트 형식은 버전 업 없이 변경하지 않습니다.

### C) 멀티테넌트/인증은 “중앙집중”

* 현재 멀티테넌트 라우트는 헤더 기반 인증 컨텍스트를 사용합니다. 
* 리뉴얼 원칙:

  * 인증/테넌트 확정은 **미들웨어/의존성 한 곳에서만** 합니다.
  * 로직 코드(핸들러/유스케이스)는 `TenantContext` 같은 “검증된 컨텍스트”만 받습니다.
  * 헤더를 여기저기서 직접 읽고 판단하는 패턴은 금지.

### D) LLM 호출은 반드시 “LLM Gateway”를 통해서만

* 지금도 LLM 호출은 `LLMAdapter`로 추상화가 일부 되어 있습니다. (deepseek/openai 선택, OpenAI 호환 클라이언트 사용) 
* 또한 LLM 호출에 대해 purpose/model/provider/ms 등을 로깅하는 좋은 패턴이 이미 존재합니다. , 
* 리뉴얼 규칙:

  1. **어떤 라우트/에이전트/서비스도 provider를 직접 호출하지 않는다.**
     (OpenAI/Gemini/Ollama/httpx 직접 호출 금지)
  2. LLM 호출은 “목적(purpose)”을 반드시 포함한다. (예: `ticket.analyze`, `ticket.fields_only`, `chat.answer`, `search.filter_extract`)
  3. **Local-first**: 가능한 케이스는 Local 모델로 처리하고, 실패/타임아웃/품질저하 시 Cloud로 폴백
  4. **타임박스 & 폴백 정책은 코드에 명시**: “몇 초 안에 안 나오면 무엇을 반환할지”를 규정
  5. 프롬프트/결과는 **절대 로그에 원문을 찍지 않는다**(길이/해시/메타만)

### E) 스트리밍은 “형식 고정 + 첫 응답 빠르게”

* 현재 스트리밍은 라우트마다 포맷이 다릅니다.

  * `/api/chat/stream`, `/api/chat/stream`(multitenant)은 `event: ...\ndata: ...\n\n` 포맷 , 
  * `/api/assist/analyze/stream`은 `data: {json}\n\n` 포맷 + 내부 `type` 필드 
* 리뉴얼 규칙:

  * **기존 엔드포인트의 이벤트 포맷은 변경 금지**(프론트 깨짐 위험이 큼)
  * 대신 신규 v1 엔드포인트에서 표준을 정하고, 기존은 점진적으로 교체/유지
  * “첫 이벤트 < 1초”를 위해, 무거운 작업(대화 수집/검색/합성)은 **가능하면 비동기/단계화**
    예: assist가 fieldsOnly일 때 대화 수집을 생략하는 최적화는 유지/확장 
    retrieve 자체도 fieldsOnly면 스킵하는 구조가 이미 있습니다. 

### F) 테스트/PR 규칙(리뉴얼을 “안전하게” 만드는 최소 조건)

* 이 리포는 pytest 기반이며 , 외부 API는 호출하지 말고 dependency override/mock을 권장합니다. 
* PR은 작게 쪼개야 합니다. 
* PR 설명에는 요구사항 체크리스트 + 근거(파일/라인)가 필요합니다. 

## 1.4. 금지사항(코덱스/코파일럿이 절대 하면 안 되는 것)

* “리팩토링 김에” API/이벤트/모델 이름을 광범위하게 바꾸기
* 라우트에서 OpenAI/Gemini/httpx를 바로 호출하기
* 프롬프트/티켓 본문/대화 전문을 로그에 남기기
* 타임아웃/폴백 없이 LLM을 호출해 요청을 무한 대기시키기
* 테스트 없이 동작 변경하기

## 1.5. Definition of Done (PR 체크리스트)

PR마다 아래를 강제합니다.

* [ ] 변경 목적이 1~2문장으로 설명된다
* [ ] 변경 범위가 작고, 비관련 변경이 없다 
* [ ] `pytest -q` 통과 
* [ ] API 변경 시 `uvicorn app.main:app --reload`로 스모크 테스트 근거가 있다 
* [ ] 요구사항 체크리스트 + 파일/라인 근거를 PR에 포함 
* [ ] LLM 호출이 있으면: purpose/provider/model/ms 로깅 + 타임아웃 + 폴백 + 테스트가 있다

---

# 2) PR 로드맵 + PR별 지침(“작게 쪼개서” 리뉴얼)

> 목표: 한 번에 갈아엎지 말고, **관측 → 게이트웨이 → 로컬기본/폴백 → 채널별 BFF 정리** 순서로 갑니다.

## PR0. 리뉴얼 가드레일 추가(문서/템플릿)

**목표**

* 방금의 “Core Design Contract”를 repo에 넣고, PR 템플릿/체크리스트를 만든다.

**변경(예시)**

* `docs/renewal/CORE_DESIGN_CONTRACT.md` (이 문서)
* `docs/renewal/PR_ROADMAP.md`
* `.github/pull_request_template.md` (요구사항 체크리스트 포함)

**완료 기준**

* 팀/AI가 다음 PR부터 이 규칙을 따라가게 됨

---

## PR1. “LLM 병목” 관측(Observability) 먼저 박기

**목표**

* 어디서 느린지 “감”이 아니라 숫자로 보이게 만들기.

**핵심 작업**

* request_id/correlation_id(미들웨어) 추가
* 주요 구간 타이밍 로그 표준화:

  * conversations enrichment, retrieve, analyze, synthesize, LLM call, RAG call 등
* LLM 호출은 이미 목적/모델/시간 로깅 패턴이 있으니  이 패턴을 **전 구간으로 확장**

**완료 기준**

* 로그만 봐도 “어느 단계가 느린지” 바로 보임
* 기능 변화 없음(리팩토링 PR이 아니라 계측 PR)

---

## PR2. LLM Gateway 뼈대 추가(행동 변화 없음)

**목표**

* “LLM 호출 단일 진입점”을 만들어서, 이후 PR에서 정책을 얹을 수 있게 하기.

**핵심 작업(권장 구조)**

* `app/llm/` 패키지 신설(권장)

  * `types.py` (Request/Response, purpose, json_mode 등)
  * `providers/` (openai_compat, local_ollama 등)
  * `gateway.py` (route + fallback + timeout + logging + cache hook)
* 기존 `LLMAdapter`는 바로 없애지 말고, “openai_compat provider” 내부 구현으로 흡수/위임

**완료 기준**

* 기존 기능은 동일하게 동작
* 코드베이스 내에서 “LLM 호출은 gateway를 통해서만”이 기술적으로 강제됨

---

## PR3. Local‑first + Fallback 정책 추가(Feature Flag로)

**목표**

* “기본은 Local, 안 되면 Cloud”를 **설정 기반으로** 적용 가능하게.

**핵심 작업**

* Settings에 local provider 설정 추가(예: `local_llm_base_url`, `local_llm_model`, `llm_route_policy`)
  기존 Settings 패턴을 따르기 
* Gateway에 정책 추가:

  * local timeout (예: 800~1500ms)
  * cloud timeout (예: 3000~8000ms)
  * 폴백 조건(타임아웃/5xx/파싱 실패)
* “작고 확실한” 기능부터 local-first 적용:

  * JSON 추출/분류/필드 제안 같이 **정형 출력 + 짧은 컨텍스트**
    예: `propose_fields_only`는 이미 경량화(스키마 compact + conversations 제거)  라서 최적 타겟

**완료 기준**

* 설정을 켜면 local-first로 동작하고, 끄면 기존과 동일
* 폴백 시에도 응답 스키마는 유지

---

## PR4. “병목 1순위 플로우”에 Gateway 적용(Assist/Analyze 계열)

**목표**

* 프론트가 느리다고 체감하는 구간(assist 분석/필드제안)을 실제로 단축.

**핵심 작업**

* `app/agents/analyzer.py` 쪽에서 LLMAdapter 직접 생성/호출을 없애고 gateway 의존으로 전환
* fieldsOnly 모드 최적화 유지/확장:

  * 대화 전체 수집 생략 
  * retrieve/synthesize 생략 
* 스트리밍은 기존 포맷 유지(중요!) 

**완료 기준**

* fieldsOnly 모드 P95가 의미 있게 내려감(계측으로 증명)
* SSE 첫 이벤트가 더 빨리 나옴

---

## PR5. Chat 경로 정리 + 채널 BFF로 정돈(점진적)

**목표**

* 다수 프론트를 지원하되, 라우팅/권한/입출력 변환은 “채널 BFF”, 로직은 “Core”로.

**핵심 작업**

* `/api/chat` / `/api/multitenant/chat` 의 중복/혼재를 “새 v1 엔드포인트”로 정리
* 기존 엔드포인트는 유지하되, 내부적으로 새 Core usecase를 호출하도록 점진 전환
* 스트리밍 이벤트 포맷은 기존 유지 

**완료 기준**

* 신규 `/api/{channel}/v1/...` 경로가 생기고, 신규 개발은 이 경로로만 진행
* 레거시 경로는 deprecate 계획이 문서화됨

---

# 3) 코덱스/코파일럿 프롬프트 팩(복붙해서 바로 작업 시작)

아래는 **그대로 복사해서 코덱스/코파일럿에 넣으면** “PR 단위로 안전한 변경”이 나오도록 구성했습니다.

## 3.1. 세션 시작 프롬프트(공통 “시스템 지시문” 역할)

> 코덱스/코파일럿에 작업을 시킬 때, 매번 맨 위에 붙이세요.

```text
당신은 wedosoft/agent-platform 리포지토리의 리뉴얼을 돕는 코드 어시스턴트입니다.
목표: 다수 프론트를 지원하는 통합 백엔드를 채널 BFF + Core + Infra로 정돈하고, LLM 병목을 해결합니다.

절대 규칙:
- 기존 API/응답/스트리밍 이벤트 포맷을 깨는 변경 금지(버전 업 없이 breaking change 금지).
- 외부 서비스(OpenAI/Gemini/httpx)를 라우트/유스케이스에서 직접 호출 금지. 모든 LLM 호출은 LLM Gateway를 통해서만.
- app/services는 얇은 어댑터로 유지하고, 순수 로직은 Core로 분리.
- PR은 작게. 한 PR에 한 목적.
- 테스트는 pytest -q 통과. 네트워크 호출은 mock/override.

작업 산출물:
- 변경 파일 목록
- 핵심 변경 요약
- 테스트/검증 방법
- 위험/롤백 포인트
```

---

## 3.2. PR0 프롬프트(문서/템플릿 넣기)

```text
[PR0] docs/renewal/CORE_DESIGN_CONTRACT.md, PR_ROADMAP.md, AI_PROMPTS.md를 추가하고
.github/pull_request_template.md에 체크리스트를 넣어주세요.

조건:
- 문서만 추가(런타임 코드 변경 금지)
- 체크리스트에는 "pytest -q", "요구사항-파일/라인 근거" 항목 포함
- 한국어로 작성
```

---

## 3.3. PR1 프롬프트(관측/타이밍)

```text
[PR1] LLM/RAG 병목 관측을 위해 request_id 기반 로그/타이밍을 추가하세요.

요구사항:
- FastAPI middleware로 request_id 생성(요청 헤더에 있으면 사용, 없으면 생성)
- 로그에 request_id 포함
- assist analyze stream, chat stream, conversations enrichment 등에 단계별 ms 로그 추가
- 기능 동작 변화는 최소화

검증:
- pytest -q
- uvicorn으로 실행 후 /api/assist/analyze/stream 요청 시 started/searching/analyzing 단계 로그가 남는지 확인
```

---

## 3.4. PR2 프롬프트(LLM Gateway 뼈대)

```text
[PR2] app/llm/ 하위에 LLM Gateway 구조를 추가하세요(기능 변화 없이).

요구사항:
- gateway.py: generate(purpose, system_prompt, user_prompt, json_mode, timeout_ms, route_policy)
- providers/openai_compat.py: 기존 LLMAdapter 또는 AsyncOpenAI를 감싸서 구현
- 기존 코드는 동작 그대로 유지하되, 앞으로 LLM 호출은 gateway를 사용하도록 "호출 위치 1곳"만 예시로 전환(예: propose_fields_only 경로)
- 프롬프트 원문을 로그에 남기지 말고 길이/모델/목적/ms만 기록

검증:
- pytest -q
- 기존 API 응답 스키마 변화 없음
```

---

## 3.5. PR3 프롬프트(Local‑first + fallback)

```text
[PR3] Local-first + Cloud fallback 정책을 LLM Gateway에 추가하세요(Feature flag 기반).

요구사항:
- Settings에 local_llm_base_url, local_llm_model, llm_route_policy, local_timeout_ms, cloud_timeout_ms 추가
- local provider(예: Ollama 호환 HTTP API) 구현은 최소 기능으로
- Local timeout/실패 시 Cloud로 폴백
- 목적(purpose)별로 어떤 경로를 local로 보낼지 정책화

검증:
- pytest -q
- 환경변수 없이도(기본값) 기존 동작 유지
```

---

## 3.6. PR4 프롬프트(Assist 경로 적용)

```text
[PR4] assist 분석/필드제안 경로에 LLM Gateway를 적용하세요.

요구사항:
- fieldsOnly 모드에서는 conversations 수집과 retrieve/synthesize를 최대한 생략(현재 최적화 유지)
- analyze_ticket_agent 내부에서 LLMAdapter 직접 생성/호출을 제거하고 gateway 주입/사용
- SSE 이벤트 포맷은 기존 그대로 유지

검증:
- pytest -q
- /api/assist/field-proposals, /api/assist/analyze/stream 동작 확인
- timingMs/로그로 전후 비교 가능하게
```

---

## 3.7. “리뷰 전용 프롬프트”(코드 어시스턴트로 셀프 리뷰)

```text
지금 PR의 변경사항을 리뷰어 관점에서 점검해 주세요.

체크:
1) Breaking change 가능성(라우트/스키마/스트리밍 이벤트)
2) LLM 호출이 gateway를 우회하는 부분이 남아있는지
3) 타임아웃/폴백/예외 처리 빈틈
4) 테스트 적절성(네트워크 호출 제거, edge/failure 케이스)
5) 롤백이 쉬운지(기능 플래그/설정)
결과는 구체적으로: 문제점, 근거(파일/함수), 수정 제안
```

---

## 3.8. 커밋/PR 작성 가이드(코파일럿이 흔히 놓치는 부분)

* 커밋 프리픽스는 conventional commits를 따르세요. 
  예: `feat: add llm gateway skeleton`, `chore: add renewal docs`, `refactor: route llm calls via gateway`
* PR 설명에는:

  * 목적/변경점/테스트 근거
  * 요구사항 체크리스트 + 파일/라인 근거 
  * API 변경 시 샘플 요청/응답 (또는 SSE 이벤트 샘플)

---

## 마지막으로(추천 운영 방식, 딱 잘라 말씀드리면)

* **“지침서(계약서) → PR0 → PR1(관측) → PR2(게이트웨이) → PR3(Local-first) → PR4(핵심 플로우 적용)”** 이 순서가 가장 안전합니다.
* 반대로 “바로 라우트 정리/대규모 구조개편”부터 들어가면, **병목 개선 효과는 늦게 나오고 리스크만 커집니다.**
* 지금 repo에는 이미 **경량 모드(fieldsOnly), 스키마 compact, 단계별 스트리밍** 같은 “좋은 최적화 씨앗”이 있습니다. ,  이걸 중심으로 Local-first를 얹는 게 효율이 가장 좋습니다.

원하시면, 다음 단계로 제가 **PR2(LLM Gateway) 설계안을 더 구체화해서**

* 파일 트리(어디에 뭘 둘지)
* 인터페이스(함수 시그니처/타입)
* local provider(Ollama 기준) 최소 구현 스펙
  까지 “코덱스가 바로 코딩 시작할 정도”로 더 쪼개서 드리겠습니다.
