# Agent Platform Handover

## 1. 프로젝트 개요
- **목표**: Google File Search 도구에서 검증된 RAG 성능과 출처 표기를 FastAPI 백엔드로 이식해 멀티 에이전트(우선 Freshservice/SKB)에서 재사용.
- **핵심 구성요소**
  - 테넌트 기반 설정(`config/tenants.local.json`)으로 제품·스토어·메타 필터를 선언적으로 관리
  - `/api/agents/*` 라우트: 세션 생성, 상태 조회, 사용자 쿼리를 Gemini File Search + Freshdesk 검색에 연결
  - `AgentChatService`: analyzer 결과 + 제품 메타 필터 + Freshdesk 검색 계획을 하나의 응답 페이로드로 묶음

## 2. 현재 완료 사항
| 영역 | 상세 내용 |
| --- | --- |
| 테넌트 로딩 | `TenantRegistry`가 env 문자열 또는 파일 경로(`AGENT_PLATFORM_TENANT_CONFIG_PATH`)에서 구성을 불러옴 |
| 세션 관리 | `/api/session` 및 `/api/agents/{tenant}/session`가 동일한 TTL/타임스탬프 포맷으로 세션 저장 |
| RAG 필터링 | `commonProduct` 요청 파라미터가 우선순위로 메타데이터 필터·필터 요약에 반영돼 제품별 검색을 강제 |
| Freshdesk 연동 | Analyzer와 Freshdesk Search Service가 ticket ID → metadata filter 형태로 RAG와 연계 |
| 테스트 | `tests/test_agent_chat_service.py`, `tests/test_agents.py` 추가. `source venv/bin/activate && pytest tests/test_agent_chat_service.py tests/test_agents.py` 통과 확인 |

## 3. 남은 과제 / 다음 단계
1. **프런트엔드 연동**
   - Next.js(또는 google-file-saerch-tool)에서 기존 `/pipeline/*` 호출 대신 `/api/agents/{tenant}` 엔드포인트 사용하도록 전환
   - `commonProduct` 라디오/셀렉트 값을 그대로 전달해 제품 고정 필터가 동작하는지 확인
2. **추가 테넌트 정의**
   - `config/tenants.local.json`에 다른 제품군(예: Monday.com, Google Workspace)을 추가하고 QA
   - 운영 환경에서는 동일 구조의 JSON을 Secrets Manager 또는 ConfigMap으로 주입
3. **Freshdesk 자격 정보**
   - `.env.local`에 `AGENT_PLATFORM_FRESHDESK_DOMAIN`, `AGENT_PLATFORM_FRESHDESK_API_KEY`를 채워 실제 티켓 검색 플로우 검증
4. **스모크 테스트**
   - `uvicorn app.main:app --reload`로 서버를 띄운 뒤 Postman 혹은 curl로 `/api/agents/{tenant}/session → /chat` 순서 검증
   - 응답의 `groundingChunks`, `freshdeskTickets`가 기대 포맷인지 확인하고 로그 수집 지표 정의
5. **배포 준비**
   - `docs/DEPLOYMENT.md` 기준으로 새로운 환경 변수를 명시하고, Terraform/Infra repo에 공유

## 4. 실행 & 검증 가이드
```bash
# 가상환경 활성화
source venv/bin/activate

# FastAPI 서버 실행
uvicorn app.main:app --reload --port 8000

# 테스트
pytest tests/test_agent_chat_service.py tests/test_agents.py
```

## 5. 리스크 & 메모
- 테넌트 JSON이 비어 있으면 `/api/agents/*` 테스트가 실패하므로 CI 전에 최소 1개 테넌트 유지 필수
- Gemini File Search Store 이름은 Google Cloud 콘솔에서 발급된 그대로 사용해야 하며, 잘못 기입 시 HTTP 500이 발생
- Freshdesk API Key 미설정 시 티켓 검색이 자동으로 비활성화되므로, 해당 상태에 대한 UX 표시가 필요할 수 있음

필요 시 Slack #agent-platform 채널에서 이전 작업자(@alan)에게 문의하면 빠르게 히스토리를 확인할 수 있습니다.
