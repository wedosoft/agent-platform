아래는 **PR3(Local‑first + Cloud fallback) 작업지시서 완성본**입니다.
PR2(LLM Gateway)가 머지됐다는 전제로, **로컬(OpenAI‑compatible) 모델을 “기본 경로”로 쓰고, 실패/지연 시 클라우드로 폴백**되도록 “구조+설정+테스트”까지 한 번에 끝내는 PR입니다.

---

# PR3 작업지시서 완성본

## 제목

**PR3: Local‑first + Cloud fallback 라우팅(목적 기반) + 타임아웃 + 테스트**

---

## 0) 전제조건(필수)

* **PR2(LLM Gateway) 머지 완료**: `app/services/llm_gateway.py`가 존재하고, `LLMAdapter`가 Gateway를 통해 호출한다.
* **PR0 머지 완료**: analyzer 관련 테스트가 그린 상태.

> PR3는 “로컬 모델 연결 + 목적별 라우팅/타임아웃/폴백”이 핵심이라 PR2가 없으면 진행이 꼬입니다.

---

## 1) 배경(왜 PR3를 지금 해야 하나)

### 1-1. 지금 병목은 “필드 제안(fieldsOnly)”이 가장 크고, 경량 최적화가 이미 들어가 있습니다

* `/assist/analyze/stream`은 `fieldsOnly=true`일 때 **conversations 전체 수집을 기본 생략**해서 병목을 줄이려는 의도가 이미 있습니다. 
* `/assist/field-proposals`는 아예 `fieldsOnly=true`를 강제하고 **Analyzer만 직접 실행(그래프/검색/합성 단계 생략)**합니다. 
* Analyzer는 `fieldsOnly`면 `LLMAdapter.propose_fields_only()`를 호출합니다. 

그리고 `propose_fields_only`는:

* 티켓 필드 스키마를 **compact**로 줄이고(nested_field 제외 등) 
* user prompt에서 무거운 키들을 제거합니다(conversations, ticket_fields 등). 
* nested_field는 LLM에게 맡기지 말고 “규칙 기반 후처리로 처리”하도록 이미 명시되어 있습니다.  

즉, **로컬 모델로 돌리기 가장 좋은 구간이 이미 만들어져 있습니다.**
PR3는 그걸 “라우팅 정책 + 폴백”으로 제품화하는 단계입니다.

---

## 2) PR3 목표(한 문장)

**`purpose=propose_fields_only`(fieldsOnly fast path)는 로컬(OpenAI‑compatible) 모델을 우선 호출하고, 타임아웃/오류/비정상 JSON이면 클라우드(기존 llm_provider)로 자동 폴백되게 한다.**

---

## 3) PR3 비목표(이번 PR에서 하지 말 것)

* 로컬 모델 정확도 향상(파인튜닝/데이터셋/LoRA) ❌
* 캐시/배칭/큐/서킷브레이커 ❌
* 프롬프트 변경/스키마 변경 ❌
* 전체 파이프라인(analyze+retrieve+synthesize)까지 로컬 강제 ❌

  * 이번 PR은 “fieldsOnly 경량 경로”에서 **체감 속도**를 먼저 얻는 게 목적입니다.

---

## 4) 설정 키 설계(= 운영에서 켜고 끌 수 있게)

### 4-1. 왜 설정 키가 필요한가

* 로컬 모델/서버는 개발환경/운영환경/노드별로 다를 수 있습니다.
* “기본 로컬”은 **위험합니다**(서버 죽으면 즉시 장애).
  → **Feature flag + base_url/model이 갖춰졌을 때만 활성화**가 정답입니다.

### 4-2. 수정 파일

* `app/core/config.py` (Settings 추가) 

> 이 레포는 `.env`, `.env.local`을 자동 로드합니다. 
> env_prefix가 없어서 키 이름 그대로 쓰는 구조입니다. 

### 4-3. 추가할 Settings 필드(정의 그대로 구현)

`Settings`에 아래를 추가하세요:

```python
# Local LLM (OpenAI-compatible) routing
llm_local_enabled: bool = False

# e.g. "http://127.0.0.1:11434/v1" (Ollama OpenAI-compatible)
llm_local_base_url: Optional[str] = None

# some servers ignore it; keep optional
llm_local_api_key: Optional[str] = None

# required when local enabled
llm_local_model: Optional[str] = None

# which purposes should use local-first
# default: propose_fields_only only
llm_local_purposes: List[str] = Field(default_factory=lambda: ["propose_fields_only"])

# timeouts (ms)
llm_local_timeout_ms: int = 1200
llm_cloud_timeout_ms_fields_only: int = 8000
```

#### 추가 validator(콤마 분리)

`supabase_common_languages`처럼, `llm_local_purposes`도 문자열이면 콤마로 split 하게 validator를 추가하세요. 

---

## 5) 목적(purpose) 기반 라우팅 정책(핵심)

### 5-1. 라우팅 표(이번 PR 기준 “고정 정책”)

| purpose               | route(순서)                | 설명                                     |
| --------------------- | ------------------------ | -------------------------------------- |
| `propose_fields_only` | `[local, cloud_primary]` | **로컬 우선 + 실패/타임아웃/비정상 JSON이면 클라우드 폴백** |
| `analyze_ticket`      | `[cloud_primary]`        | 이번 PR에서는 기본 유지                         |
| `propose_solution`    | `[cloud_primary]`        | 이번 PR에서는 기본 유지                         |

* `cloud_primary`는 기존처럼 `settings.llm_provider` 입니다. 
* 로컬이 꺼져있거나 설정이 불완전하면(local_enabled=false 또는 base_url/model 미설정) **라우트에서 local을 제외**해야 합니다.

### 5-2. 왜 `propose_fields_only`만 로컬 우선인가

이 경로는 이미:

* 입력이 작고(필드 스키마 compact) 
* conversations 등 거대한 컨텍스트를 제거하며 
* nested_field는 룰 기반 후처리로 안전장치가 있어서  
  작은 로컬 모델로도 성능을 뽑기 쉬운 구간입니다.

---

## 6) 타임아웃 정책(숫자까지 고정)

### 6-1. 이번 PR에서 적용할 기본값(설정으로 변경 가능)

* **local timeout**: `1200ms`

  * 로컬이 느리면 “로컬을 쓰는 의미”가 사라지므로, **빠르게 끊고 폴백**이 맞습니다.
* **cloud timeout (fieldsOnly)**: `8000ms`

  * 최악의 경우 총 대기 시간은 대략 `1.2s + 8s = 9.2s` 수준으로 제한됩니다.

### 6-2. “비정상 JSON”도 폴백 조건에 포함(강제)

`propose_fields_only`는 `json.loads(response)`를 바로 하기 때문에 ,
로컬 모델이 JSON을 망치면 즉시 예외가 납니다.

따라서 **Gateway에서 `json_mode=True`면**:

* 결과 텍스트가 **JSON object로 파싱되는지** 최소 검증하고,
* 파싱 실패 시 provider 실패로 간주하여 **다음 provider로 폴백**하세요.

(스키마까지 검증하진 말고, “파싱 가능”까지만 하십시오. 이번 PR 범위에서 충분합니다.)

---

## 7) 구현 상세(파일별 작업 지시)

## 7-1. `app/services/llm_gateway.py` (PR3 핵심 수정)

### 요구사항

1. **Local provider 등록**

* `settings.llm_local_enabled == True` AND `llm_local_base_url` AND `llm_local_model` 이면

  * providers에 `"local"`을 등록 (OpenAI-compatible Provider로)
  * api_key는 `llm_local_api_key`가 없으면 `"ollama"` 같은 더미 문자열을 사용(클라이언트 생성 실패 방지)

2. **purpose_routes 구성**

* 기본: `default_route = [settings.llm_provider]`
* local-first: `purpose_routes[purpose] = ["local", settings.llm_provider]`
  단, local provider가 등록된 경우에만

3. **route 선택 로직**

* `gateway.generate(req)` 호출 시, 외부에서 route가 안 들어오면:

  * `purpose_routes.get(req.purpose, default_route)`를 사용

4. **provider별 timeout 선택**

* req.timeout_ms가 명시되면 그걸 우선
* 아니면:

  * provider == "local": `settings.llm_local_timeout_ms`
  * provider != "local" AND purpose == "propose_fields_only": `settings.llm_cloud_timeout_ms_fields_only`
  * 그 외: timeout 적용하지 않음(또는 매우 큰 값)
    → 이번 PR은 fieldsOnly만 확실히 개선하면 됩니다.

5. **json_mode=True일 때 JSON 파싱 검증**

* 파싱 실패 시 `ValueError` 등을 던져서 다음 provider로 폴백되게 만들 것

---

## 7-2. `app/core/config.py` (Settings 추가)

* 위 4-3 정의대로 Settings 필드 추가
* `llm_local_purposes` 콤마 split validator 추가

기존 LLM provider 설정은 그대로 유지합니다. (`llm_provider`, `deepseek_api_key`, `openai_api_key`) 

---

## 7-3. `app/services/llm_adapter.py` (PR3에서 변경 최소)

PR2에서 이미 Adapter가 Gateway를 호출하도록 바뀌어 있을 겁니다.
PR3에서는 다음만 확인/정리하세요:

* `generate(... purpose="propose_fields_only", json_mode=True)`처럼 **purpose는 정확히 전달**되어야 함
* timeout은 Adapter에서 직접 박지 말고(또는 fieldsOnly만 박고), **gateway 정책을 우선**하게 유지

> 목적 기반 라우팅이니까 Adapter가 route를 선택하면 안 됩니다. Adapter는 purpose만 넘기고 끝내는 게 맞습니다.

---

## 8) 테스트(네트워크 없이, PR3에서 반드시 추가/수정)

### 8-1. 테스트 파일

* (PR2에서 만들었던) `tests/test_llm_gateway.py`를 확장하거나,
* 새로 `tests/test_llm_gateway_routing.py`를 추가

### 8-2. 필수 테스트 케이스 4개

1. **local-first route가 purpose에 의해 선택되는지**

* gateway에 `purpose_routes={"propose_fields_only": ["local", "cloud"]}` 넣고
* req.purpose="propose_fields_only"로 호출 시 local이 먼저 호출되는지 확인

2. **local 성공 시 cloud가 호출되지 않는지**

* local provider: 즉시 성공
* cloud provider: 호출되면 테스트 실패로 만들기(또는 calls==0 assert)

3. **local timeout 시 cloud로 폴백되는지**

* local provider: `await sleep(0.2)`
* local timeout_ms: 10ms 같은 값으로 설정
* cloud provider: 즉시 성공
* 기대: 반환 provider가 cloud, attempts==2, used_fallback==True

4. **local이 JSON을 망치면 폴백되는지(json_mode 검증)**

* local provider: `"NOT JSON"` 반환
* req.json_mode=True
* cloud provider: 정상 JSON 반환
* 기대: 결과가 cloud에서 왔고, 예외 없이 성공

---

## 9) 검증(개발자가 실제로 해야 하는 명령)

* `pytest -q`

그리고(선택) 로컬 테스트:

1. `.env.local`에 아래를 넣고 
2. `/assist/field-proposals`를 호출했을 때 로그에 provider=local이 찍히는지 확인

### `.env.local` 예시

```bash
LLM_PROVIDER=deepseek

LLM_LOCAL_ENABLED=true
LLM_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
LLM_LOCAL_MODEL=llama3.1:8b-instruct-q4_K_M
LLM_LOCAL_TIMEOUT_MS=1200
LLM_CLOUD_TIMEOUT_MS_FIELDS_ONLY=8000
LLM_LOCAL_PURPOSES=propose_fields_only
```

---

## 10) Copilot/Codex용 작업지시 프롬프트(복붙용)

아래는 **한 번에 다 던지지 말고** 1→2→3 순서로 던지세요.

### 프롬프트 1/3 — 계획만 작성

```text
PR3(Local-first + Cloud fallback) 구현 계획을 12줄 이내로 작성하세요.

조건:
- 목적(purpose) 기반 라우팅: propose_fields_only는 local -> cloud_primary, 나머지는 cloud_primary 유지
- local은 OpenAI-compatible base_url/model로 연결 (Settings로 제어)
- local timeout 1200ms, cloud(fieldsOnly) timeout 8000ms
- json_mode=True일 때 output이 JSON 파싱 불가하면 fallback
- 네트워크 호출 없는 테스트 4개 추가
산출물: 변경 파일 목록 + 각 파일의 구현 체크리스트
```

### 프롬프트 2/3 — 설정+게이트웨이 구현

```text
PR3 구현을 진행하세요.

작업:
1) app/core/config.py(Settings)에 아래 필드 추가:
- llm_local_enabled(bool, default False)
- llm_local_base_url(Optional[str])
- llm_local_api_key(Optional[str])
- llm_local_model(Optional[str])
- llm_local_purposes(List[str], default ["propose_fields_only"]) + 콤마 split validator
- llm_local_timeout_ms(int, default 1200)
- llm_cloud_timeout_ms_fields_only(int, default 8000)

2) app/services/llm_gateway.py 수정:
- local_enabled && base_url && model이면 "local" provider 등록(OpenAI-compatible)
- purpose_routes 구성: propose_fields_only -> ["local", settings.llm_provider] (local이 있을 때만)
- generate()에서 route가 없으면 purpose_routes 기반으로 선택
- timeout 정책: local은 llm_local_timeout_ms, cloud(fieldsOnly)은 llm_cloud_timeout_ms_fields_only
- json_mode=True면 결과 텍스트가 JSON object로 파싱 가능한지 최소 검증하고 실패 시 fallback

제약:
- 프롬프트 내용/LLMAdapter 프롬프트는 변경하지 말 것
- 로그에 프롬프트 원문 남기지 말 것(길이/메타만)
- diff는 PR3 범위(라우팅/설정/테스트)에만 집중
```

### 프롬프트 3/3 — 테스트 추가

```text
네트워크 없이 PR3 테스트를 추가/수정하세요.

필수 테스트 4개:
1) propose_fields_only 목적에서 local-first route 선택
2) local 성공 시 cloud 미호출
3) local timeout 시 cloud fallback (used_fallback=True, attempts==2)
4) json_mode=True에서 local이 "NOT JSON" 반환하면 cloud fallback

StubProvider로 gateway에 providers/purpose_routes/timeouts를 주입해서 테스트하세요.
검증: pytest -q
```

---

## 11) PR3 완료 기준(DoD)

* `pytest -q` 통과
* `propose_fields_only`에서:

  * local 설정이 켜져있고 정상일 때 **local 먼저**
  * local이 느리거나/죽었거나/JSON을 망치면 **cloud로 자동 폴백**
* 로컬 설정이 꺼져있으면 기존과 동일하게 cloud만 사용(회귀 없음)

---

원하시면, PR3 다음으로 바로 이어서 **PR4(캐시/서킷브레이커/동시성 제한/프롬프트 분할)** 작업지시서도 같은 방식으로 만들어드릴 수 있습니다.
하지만 지금 흐름에서는 PR3까지 끝나면 “속도 체감”은 거의 나올 가능성이 높습니다.
