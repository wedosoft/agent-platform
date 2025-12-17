아래는 **PR2(LLM Gateway) 작업지시서 완성본**입니다.
이 문서대로 하면 **Copilot/Codex가 “바로” 구현을 시작**할 수 있고, PR3(Local‑first+fallback)로 자연스럽게 연결됩니다.

---

# PR2 작업지시서 완성본

## 제목

**PR2: LLM Gateway 도입(목적 기반 호출/라우팅/타임아웃/폴백 기반 마련)**

---

## 1) 배경과 현재 상태(왜 이 PR이 필요한가)

### 1-1. 지금 LLM 호출은 `LLMAdapter`에 과도하게 결합돼 있습니다

`LLMAdapter`는 설정(`llm_provider`)을 읽어서 provider/키/base_url/모델을 내부에서 결정하고, `AsyncOpenAI`로 직접 호출합니다.  
→ 이 구조에서는 “로컬 우선 → 실패/타임아웃이면 클라우드 폴백” 같은 정책을 **중앙에서 통제하기 어렵습니다**.

### 1-2. 호출 지점이 여러 군데라 정책이 흩어질 위험이 큽니다

* Analyzer는 `fieldsOnly`면 `propose_fields_only`, 아니면 `analyze_ticket`을 호출합니다. 
* Synthesizer/Resolver도 `propose_solution`을 각각 호출합니다.  
  → 라우트/에이전트/서비스마다 각자 timeout/fallback/cache를 붙이기 시작하면 **아키텍처가 금방 붕괴**합니다.

### 1-3. 목적(purpose) 기반 로깅은 이미 좋은 패턴이 있습니다

`analyze_ticket`, `propose_fields_only`, `propose_solution`마다 “purpose=…” 형태로 로깅하고 있습니다.   
→ 이걸 **Gateway로 승격**시키면 “목적별 라우팅/타임아웃/폴백”을 붙이기 딱 좋습니다.

---

## 2) PR2 목표(한 문장)

**LLM 호출을 “LLM Gateway” 단일 진입점으로 모으고, 목적(purpose) 기반 라우팅/타임아웃/폴백을 PR3에서 추가할 수 있도록 구조를 만든다(기능/출력은 최대한 동일 유지).**

---

## 3) PR2 비목표(이번 PR에서 하지 말 것)

* 로컬 모델(Ollama/llama.cpp) 실제 연결 ❌ (PR3에서)
* 캐시/배칭/큐/서킷브레이커 ❌ (PR4~에서)
* 프롬프트 내용 변경 ❌ (정확도/회귀 리스크 큼)
* API 엔드포인트/응답 스키마/스트리밍 포맷 변경 ❌
* 대규모 폴더 구조 개편 ❌ (이번 PR은 “게이트웨이 도입”만)

---

## 4) 설계 원칙(레포 가이드라인 준수)

* `app/services`는 외부 I/O 어댑터를 얇게 유지하고 순수 로직을 분리합니다. 
* 테스트는 `pytest -q`, 네트워크 호출 대신 override/mock을 우선합니다. 
* PR은 작게, 변경 범위 집중이 원칙입니다. 
* PR 설명은 요구사항 체크리스트 + 파일/라인 근거를 포함합니다. 

---

## 5) 변경 범위(파일 단위)

### 5-1. 신규 파일

1. `app/services/llm_gateway.py` (신규)

* Gateway 타입/인터페이스/라우팅/타임아웃/기본 provider 등록을 담당

2. `tests/test_llm_gateway.py` (신규)

* 네트워크 없이 stub provider로 timeout/fallback 동작을 검증

### 5-2. 수정 파일

1. `app/services/llm_adapter.py` (수정)

* **외부 인터페이스(메서드 이름/리턴 형태)는 유지**
* 내부 구현만 “Gateway를 통해 generate”하도록 변경

---

## 6) PR2 상세 설계(코덱스/코파일럿이 그대로 구현할 수 있게)

아래 시그니처/구조를 **그대로** 구현하도록 지시하세요.

### 6-1. `LLMRequest`, `LLMResponse` (Gateway에서 쓰는 타입)

```python
# app/services/llm_gateway.py

from dataclasses import dataclass
from typing import Optional, List, Dict, Protocol, Any

@dataclass(frozen=True)
class LLMRequest:
    purpose: str
    system_prompt: str
    user_prompt: str
    temperature: float
    json_mode: bool
    timeout_ms: Optional[int] = None  # PR2에서는 기본 None(=기존 동작 최대한 유지)

@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    latency_ms: int
    attempts: int
    used_fallback: bool
```

> **포인트:** PR2는 “구조 도입”이 목적이라 timeout 기본값을 강제하지 않습니다.
> timeout은 **테스트/향후 PR3에서만 적극 사용**하게 두는 게 안전합니다.

---

### 6-2. Provider 인터페이스(Protocol)

```python
class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, req: LLMRequest) -> str:
        ...
```

---

### 6-3. OpenAI‑compatible Provider (DeepSeek/OpenAI 둘 다 처리)

**현재 코드가 이미 “DeepSeek는 OpenAI‑compatible”로 처리하고 있으니** , Provider도 같은 방식으로 갑니다.

```python
# app/services/llm_gateway.py

import asyncio
import time
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class OpenAICompatProvider:
    def __init__(self, *, name: str, api_key: str | None, base_url: str | None, model: str):
        self.name = name
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        # ❗중요: 테스트/로컬에서 키가 없을 수 있으니, __init__에서 바로 터지지 않게 "지연 생성"
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def generate(self, req: LLMRequest) -> str:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.user_prompt},
            ],
            temperature=req.temperature,
            response_format={"type": "json_object"} if req.json_mode else None,
        )
        return response.choices[0].message.content
```

> 위 호출 형태는 현재 `LLMAdapter.generate()`가 쓰는 방식과 동일하게 맞춥니다. 

---

### 6-4. `LLMGateway` (라우팅/타임아웃/폴백의 “뼈대”)

```python
class LLMTimeoutError(Exception):
    pass

class LLMGateway:
    def __init__(self, *, providers: Dict[str, LLMProvider], default_route: List[str]):
        self.providers = providers
        self.default_route = default_route

    async def generate(self, req: LLMRequest, *, route: Optional[List[str]] = None) -> LLMResponse:
        route = route or self.default_route
        used_fallback = False
        attempts = 0
        last_err: Exception | None = None

        for idx, provider_name in enumerate(route):
            attempts += 1
            provider = self.providers.get(provider_name)
            if provider is None:
                last_err = ValueError(f"Unknown provider: {provider_name}")
                continue

            t0 = time.perf_counter()
            try:
                if req.timeout_ms:
                    content = await asyncio.wait_for(provider.generate(req), timeout=req.timeout_ms / 1000)
                else:
                    content = await provider.generate(req)

                latency_ms = int((time.perf_counter() - t0) * 1000)
                if idx > 0:
                    used_fallback = True

                # ✅ 로그는 프롬프트 원문 금지(길이/메타만)
                logger.info(
                    "LLM done purpose=%s provider=%s model=%s json_mode=%s sys_chars=%s user_chars=%s ms=%s attempts=%s fallback=%s",
                    req.purpose,
                    provider.name,
                    provider.model,
                    req.json_mode,
                    len(req.system_prompt),
                    len(req.user_prompt),
                    latency_ms,
                    attempts,
                    used_fallback,
                )

                return LLMResponse(
                    content=content,
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=latency_ms,
                    attempts=attempts,
                    used_fallback=used_fallback,
                )

            except asyncio.TimeoutError as e:
                last_err = LLMTimeoutError(f"Timeout provider={provider_name} purpose={req.purpose}")
            except Exception as e:
                last_err = e

        # 모두 실패
        assert last_err is not None
        raise last_err
```

---

### 6-5. `get_llm_gateway()` (설정 기반 default gateway 생성)

Settings에 `llm_provider/deepseek_api_key/openai_api_key`가 이미 있습니다. 
현재 `LLMAdapter`가 사용하던 기본 매핑도 그대로 유지합니다. 

```python
from functools import lru_cache
from app.core.config import get_settings

@lru_cache
def get_llm_gateway() -> LLMGateway:
    s = get_settings()
    providers = {
        "deepseek": OpenAICompatProvider(
            name="deepseek",
            api_key=s.deepseek_api_key,
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
        ),
        "openai": OpenAICompatProvider(
            name="openai",
            api_key=s.openai_api_key,
            base_url=None,
            model="gpt-4o-mini",
        ),
    }
    default_route = [s.llm_provider.lower()]
    return LLMGateway(providers=providers, default_route=default_route)
```

> PR3에서 여기 default_route를 purpose별로 `[local, cloud]`로 확장할 예정입니다.

---

## 7) `LLMAdapter` 수정 지침(기능 유지, 내부만 Gateway로)

`LLMAdapter`의 공개 메서드(`analyze_ticket`, `propose_fields_only`, `propose_solution`)는 여러 곳에서 사용됩니다.  
따라서 **시그니처/리턴 형태는 유지**하고, 내부 `generate`만 Gateway를 거치게 바꾸세요.

### 7-1. `LLMAdapter.__init__` 변경

* `self.client/self.model/self.provider` 같은 “직접 호출 요소”는 제거하거나 최소화
* `self.gateway = get_llm_gateway()` 추가

현재는 `LLMAdapter`가 provider와 model을 자체 결정합니다. 
→ PR2에서는 이 결정을 `get_llm_gateway()`로 이전합니다.

### 7-2. `LLMAdapter.generate()` 변경(중요)

기존 시그니처는 유지하되, **키워드 파라미터로 `purpose`와 `timeout_ms`만 추가**하세요(기존 호출 깨지지 않게).

```python
async def generate(
    self,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    json_mode: bool = False,
    *,
    purpose: str = "generate",
    timeout_ms: int | None = None,
) -> str:
    req = LLMRequest(
        purpose=purpose,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        json_mode=json_mode,
        timeout_ms=timeout_ms,
    )
    res = await self.gateway.generate(req)
    return res.content
```

### 7-3. 각 메서드에서 `purpose`를 명시해서 호출

현재 로깅에서 쓰던 purpose를 그대로 `generate(... purpose="...")`로 넘기세요.

* `analyze_ticket` → `"analyze_ticket"` 
* `propose_fields_only` → `"propose_fields_only"` 
* `propose_solution` → `"propose_solution"` 

그리고 **이제 목적 로그는 Gateway에서 일괄로 찍으니**, 기존 메서드 안에 있던 `t0/logger.info("LLM done ...")` 블록은 제거해도 됩니다(중복 로그 방지).

---

## 8) 테스트 계획(네트워크 없이, PR2에서 반드시 추가)

AGENTS 가이드에 따라 네트워크 호출 없이 테스트합니다. 

### 8-1. 신규 테스트 파일

* `tests/test_llm_gateway.py` (새로 추가)

### 8-2. 테스트 케이스(필수 3개)

1. **단일 provider 성공**

* route가 1개일 때 정상 결과 + provider/model/latency가 채워지는지

2. **timeout 시 fallback 동작(핵심)**

* provider A가 의도적으로 sleep → timeout
* provider B가 즉시 성공
* 결과 provider가 B인지 + attempts=2 + used_fallback=True

3. **모든 provider 실패 시 예외**

* 모두 실패하면 예외가 올라오는지(타입/메시지 최소 확인)

### 8-3. stub provider 예시(테스트 내부)

```python
class StubProvider:
    def __init__(self, name="stub", model="m", delay=0.0, exc=None, content="ok"):
        self.name = name
        self.model = model
        self.delay = delay
        self.exc = exc
        self.content = content
        self.calls = 0

    async def generate(self, req):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.content
```

---

## 9) 검증 방법(개발자/AI가 반드시 수행)

* `pytest -q` 실행(레포 표준) 
* 추가로 PR2는 API 변경이 없으니 smoke는 선택이지만, 원칙상 API 변경 시엔 uvicorn 확인을 권장합니다.  

---

## 10) PR 리뷰 체크리스트(이 PR에서 반드시 보는 것)

* [ ] `LLMAdapter` 공개 메서드 시그니처/리턴이 바뀌지 않았는가
* [ ] OpenAI/DeepSeek 호출이 **Gateway 밖에서** 일어나지 않는가
* [ ] 로그에 **프롬프트 원문**이 남지 않는가(길이/메타만)
* [ ] timeout/fallback 테스트가 실제로 fallback을 검증하는가
* [ ] PR diff가 “Gateway 도입”에만 집중되어 있는가 

---

## 11) 롤백 플랜

* 이 PR은 코드 구조만 추가/치환하므로, 문제 시 **PR 전체 revert**하면 됩니다.
* 외부 API/스키마 변경이 없어서 롤백 비용이 낮습니다.

---

## 12) Copilot/Codex용 작업지시 프롬프트(복붙용)

아래 3개를 **순서대로** 던지시면 됩니다. (한 번에 다 던지지 마십시오. AI가 범위를 넓힙니다.)

### 프롬프트 1/3 — “계획만 작성”

```text
레포에서 app/services/llm_adapter.py를 읽고, LLM 호출을 LLM Gateway로 분리하는 PR2 계획을 10줄 내로 요약하세요.
조건:
- analyze_ticket / propose_fields_only / propose_solution의 시그니처와 리턴 형태는 유지
- 외부 네트워크 호출 없는 테스트 추가
- 새 파일: app/services/llm_gateway.py, tests/test_llm_gateway.py
산출물: 변경 파일 목록 + 각 파일에서 할 일 목록
```

### 프롬프트 2/3 — “구현”

```text
PR2 구현을 진행하세요.

작업:
1) app/services/llm_gateway.py를 새로 만들고 아래를 구현:
- LLMRequest, LLMResponse dataclass
- LLMProvider Protocol
- OpenAICompatProvider(AsyncOpenAI 호출; response_format json_mode 처리)
- LLMGateway(generate: route list + optional timeout_ms + fallback)
- get_llm_gateway(): settings.llm_provider 기반 default_route, deepseek/openai provider 등록

2) app/services/llm_adapter.py 수정:
- LLMAdapter가 AsyncOpenAI를 직접 생성/호출하지 않게 변경
- generate()가 gateway.generate()를 호출하도록 변경
- generate()에 keyword-only로 purpose, timeout_ms 추가(기존 호출 깨지지 않게)
- analyze_ticket / propose_fields_only / propose_solution에서 generate(purpose="...")로 호출
- 프롬프트 내용/JSON 파싱 로직은 그대로 유지

제약:
- API/라우트/응답 스키마 변경 금지
- 프롬프트 원문을 로그에 남기지 말 것(길이/메타만)
- diff를 LLM Gateway 도입에만 집중

산출물:
- 변경 diff 요약
- pytest -q로 통과 확인
```

### 프롬프트 3/3 — “테스트 추가”

```text
tests/test_llm_gateway.py를 추가하세요.

요구 테스트(비네트워크):
1) 단일 provider 성공
2) timeout 시 fallback(첫 provider 지연 -> timeout_ms로 실패 -> 두번째 provider 성공)
3) 모두 실패 시 예외

주의:
- 실제 OpenAI/DeepSeek 네트워크 호출 금지
- StubProvider로 gateway에 providers를 주입하여 테스트
검증: pytest -q
```

---

원하시면, 다음으로 **PR3(Local‑first + Cloud fallback)** 작업지시서도 같은 수준으로(설정 키, 목적별 라우팅 정책, 타임아웃 값, 테스트까지) 완성본으로 바로 작성해드리겠습니다.
