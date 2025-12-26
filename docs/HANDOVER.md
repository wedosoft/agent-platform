# Agent Platform Handover

## 1. 프로젝트 개요

### 1.1 목표
- **핵심 전환**: Freshdesk 티켓 "답장 생성" → "분석 리포트 생성"
- **출력 형식**: 자연어 답장이 아닌 구조화된 `ticket_analysis_v1` JSON
- **Gate 시스템**: 상담원 UI 모드 결정 (`CONFIRM`, `EDIT`, `DECIDE`, `TEACH`)

### 1.2 핵심 구성요소
- **Backend (agent-platform)**: FastAPI 기반 분석 API
- **Frontend (project-a)**: Freshdesk Custom App (FDK v3.0)
- **참고 논문**: Reflexion (2303.11366), Generative Agents (2304.03442)

### 1.3 상세 계획
- [docs/born-again/pr-instruction.md](./born-again/pr-instruction.md) - 3 PR 리팩터링 계획

---

## 2. 리팩터링 로드맵 (3 PR)

### PR1 — Schemas + Validator + Analyze API Skeleton
| 항목 | 내용 |
|------|------|
| 목적 | "스키마가 곧 법"을 코드로 강제, 프론트와 병렬 개발 가능 |
| 스키마 | `ticket_normalized_v1.json`, `ticket_analysis_v1.json` |
| API | `POST /api/tickets/{ticket_id}/analyze` |
| 에러 | 400: `INVALID_INPUT_SCHEMA`, 500: `ANALYSIS_FAILED` |

### PR2 — Orchestrator + Prompt Registry + Persist
| 항목 | 내용 |
|------|------|
| 목적 | 실제 분석 파이프라인, 재현/비교/학습 가능한 저장 |
| Prompt Registry | `ticket_analysis_cot_v1.yaml` (versioned prompts) |
| Orchestrator | `run_ticket_analysis(input, options) -> (analysis, gate, meta)` |
| DB 테이블 | `analysis_runs`, `ticket_analyses` |

### PR3 — Frontend (project-a) UI 연동
| 항목 | 내용 |
|------|------|
| 목적 | 답장 중심 UI → 분석 콘솔로 전환 |
| UI 탭 | Analyze, Evidence, Teach, History |
| 상태 머신 | `IDLE → RUNNING → COMPLETED`, `NEEDS_REVIEW`, `ERROR` |

---

## 3. CS 팀장 관점: UI/UX 분석

### 3.1 사용자 페르소나
- **대상**: Freshdesk 상담원 겸 엔지니어 (기술 지원)
- **특성**: 높은 티켓 볼륨, SLA 압박, 멀티태스킹, 기술적 배경

### 3.2 채팅 방식 vs 분석 대시보드 비교

| 평가 항목 | 채팅 방식 | 분석 대시보드 |
|-----------|-----------|---------------|
| **일관성** | ❌ 상담원별 질문 품질 편차 | ✅ 동일한 구조화된 결과 |
| **효율성** | ❌ 왕복 대화로 지연 | ✅ 원클릭 분석 |
| **측정 가능성** | ❌ 대화 품질 수치화 어려움 | ✅ Gate별 분포, 해결 시간 추적 |
| **신입 온보딩** | ❌ "좋은 질문" 학습 필요 | ✅ 구조가 워크플로우 가이드 |
| **QA** | ❌ 대화 로그 전체 검토 필요 | ✅ 구조화 데이터로 샘플링 용이 |
| **유연성** | ✅ 후속 질문/탐색 자유 | ❌ 정해진 분석 프레임 |
| **학습 진입장벽** | ✅ 자연어로 바로 사용 | ❌ 탭/섹션 의미 학습 필요 |

### 3.3 권장 아키텍처: 하이브리드 접근

```
┌─────────────────────────────────────────────────────┐
│  기본 UI: 분석 대시보드 (Primary)                     │
│  ├── Analyze: 원클릭 구조화 분석                      │
│  ├── Evidence: 근거 데이터 정리                       │
│  ├── History: 과거 분석 비교                         │
│  └── Teach: 교훈 기록                               │
├─────────────────────────────────────────────────────┤
│  보조 UI: 채팅 (Secondary, Optional)                 │
│  └── 분석 결과 기반 후속 질문용                        │
│  └── Edge case/복잡한 티켓에서만 활성화               │
└─────────────────────────────────────────────────────┘
```

### 3.4 단계별 구현 권장안

| 단계 | 내용 |
|------|------|
| **PR1-2 (MVP)** | 분석 대시보드만 구현. 채팅 탭 비활성화/제거 |
| **운영 피드백** | 1-2개월 실사용 후 "채팅이 필요했던 케이스" 수집 |
| **후속 PR** | 필요시 "Ask AI" 버튼으로 분석 결과 기반 후속 질문 추가 |

### 3.5 결론

**분석 대시보드를 Primary UI로 선택하는 이유**:

1. **표준화**: 팀 전체가 일관된 품질의 분석 결과 확보
2. **효율성**: 원클릭 → 구조화된 결과 → 고객 대기 시간 단축
3. **측정 가능**: Gate 분포, 분석 시간, Teach 수 등 KPI 추적
4. **확장성**: Lesson 축적으로 시스템 지속 개선
5. **QA 용이**: 구조화된 데이터로 품질 관리 가능

채팅 기능은 MVP 범위에서 제외하고, 실제 운영 피드백에서 강한 수요가 확인된 후 추가 권장.

---

## 4. 실행 & 검증 가이드

```bash
# 가상환경 활성화
source venv/bin/activate

# FastAPI 서버 실행
uvicorn app.main:app --reload --port 8000

# 테스트
pytest tests/
```

---

## 5. 범위 밖 (3 PR 이후)

- 유사 티켓/KB 하이브리드 검색 (Retrieval 고도화)
- Policy/Org Memory 승격 워크플로우 (PR 승인/권한)
- 고급 평가 (정교한 score_breakdown, 위험 태그 자동 분류)
- SSE/Webhook 기반 비동기 처리 (대형 티켓 대응)

---

## 6. 연락처

필요 시 Slack #agent-platform 채널에서 이전 작업자(@alan)에게 문의.

---

*Last Updated: 2025-12*
