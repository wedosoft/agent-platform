# 리뉴얼 작업용 AI 프롬프트 팩

> 목적: Codex/Copilot에게 “범위가 커지는 리뉴얼 작업”을 PR 단위로 안전하게 시키기 위한 복붙용 프롬프트입니다.
>
> 참고(불변 규칙): `docs/renewal/CORE_DESIGN_CONTRACT.md`

## 0) 세션 시작 프롬프트(매번 맨 위에 붙이기)

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

## 1) PR0-B 프롬프트(가드레일: 문서/템플릿)

```text
[PR0-B] 리뉴얼 가드레일을 추가하세요.

작업:
- docs/renewal/ 하위에 리뉴얼 문서(계약서/로드맵/프롬프트)를 정리하고,
- .github/pull_request_template.md 를 추가해 PR 체크리스트를 강제하세요.

조건:
- 런타임 코드 변경 금지(문서/템플릿만)
- 체크리스트에는 "pytest -q", "요구사항-파일/라인 근거" 항목 포함
- 모든 문서는 한국어로 작성
```

## 2) PR1 프롬프트(관측/타이밍)

```text
[PR1] LLM/RAG 병목 관측을 위해 request_id 기반 로그/타이밍을 추가하세요.

요구사항:
- FastAPI middleware로 request_id 생성(요청 헤더에 있으면 사용, 없으면 생성)
- 로그에 request_id 포함
- assist analyze stream, chat stream, conversations enrichment 등에 단계별 ms 로그 추가
- 기능 동작 변화는 최소화

검증:
- pytest -q
```

## 3) PR2 프롬프트(LLM Gateway 뼈대)

```text
[PR2] LLM Gateway 구조를 추가하세요(기능 변화 없이).

요구사항:
- LLM 호출 단일 진입점(gateway)
- 프롬프트 원문을 로그에 남기지 말고 길이/모델/목적/ms만 기록
- 네트워크 호출 없는 테스트(stub provider) 추가

검증:
- pytest -q
```

## 4) PR3 프롬프트(Local-first + fallback)

```text
[PR3] Local-first + Cloud fallback 정책을 LLM Gateway에 추가하세요(Feature flag 기반).

요구사항:
- Settings에 local base_url/model/purposes/timeout 추가
- Local timeout/실패/JSON 파싱 실패 시 Cloud로 폴백
- 목적(purpose)별로 어떤 경로를 local로 보낼지 정책화

검증:
- pytest -q
- 설정이 꺼져있으면 기존 동작 유지
```

