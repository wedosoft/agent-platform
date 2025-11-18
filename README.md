# Agent Platform Backend

FastAPI 기반의 차세대 에이전트 오케스트레이션 백엔드입니다. LangGraph, Google File Search 파이프라인, Gemini/OpenAI 기반 봇 등을 단일 API 계층으로 결합하기 위한 스켈레톤을 제공합니다.

## 개발 환경

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e '.[dev]'
```

로컬 개발 시 비밀 값은 `.env.local`에 저장하고, `.env.local.example`을 복사해 기본 값을 채운 뒤 필요에 맞게 수정하세요. Supabase 공통 문서 프로젝트 URL/Service Role Key를 제공해야 `/api/common-products`, `/api/common-documents`가 동작합니다. 또한 `GEMINI_API_KEY`(또는 `AGENT_PLATFORM_GEMINI_API_KEY`)와 `AGENT_PLATFORM_GEMINI_COMMON_STORE_NAME`을 지정하면 `/api/chat`이 공통 문서 전용 질문을 FastAPI만으로 처리합니다.

## 실행

```bash
uvicorn app.main:app --reload --port 8000
```

`AGENT_PLATFORM_PIPELINE_BASE_URL` 환경 변수를 기존 Node 파이프라인(`/pipeline` 엔드포인트 제공) URL로 설정하면, FastAPI 서버가 세션·챗 요청을 프록시합니다. 기본값은 `http://localhost:4000/pipeline`이며, 로컬에서는 `.env.local`에서 이 값을 오버라이드할 수 있습니다.

공통 문서 검색을 FastAPI에서 직접 처리하려면 Supabase 설정을 추가로 지정하세요.

```bash
AGENT_PLATFORM_SUPABASE_COMMON_URL=https://xxxx.supabase.co
AGENT_PLATFORM_SUPABASE_COMMON_SERVICE_ROLE_KEY=secret
AGENT_PLATFORM_SUPABASE_COMMON_TABLE_NAME=documents
AGENT_PLATFORM_SUPABASE_COMMON_BATCH_SIZE=25
AGENT_PLATFORM_SUPABASE_COMMON_LANGUAGES=ko,en
AGENT_PLATFORM_SUPABASE_COMMON_DEFAULT_PRODUCT=SharedDocs
```

Fly.io에서 Redis 애드온을 사용할 경우 `AGENT_PLATFORM_REDIS_URL`을 설정하면 세션/대화 기록이 Redis로 영속화되어 다중 인스턴스 배포에서도 상태가 유지됩니다. 로컬 개발 시 해당 변수를 비워두면 인메모리 저장소를 사용합니다.

기본 API prefix는 `/api`이며 현재 프록시/구현된 엔드포인트는 다음과 같습니다.

- `GET /api/health`
- `POST /api/session`
- `GET /api/session/{sessionId}`
- `POST /api/chat`
- `GET /api/status`
- `GET /api/common-products`
- `GET /api/common-documents`
- `POST /api/sync`

## 다음 단계
- LangGraph 실행기 및 Google File Search 파이프라인 어댑터 연동
- 세션/대화 기록의 영속 저장소 연결 (예: Redis, Postgres)
- 인증/권한 및 공통 SDK 제공
