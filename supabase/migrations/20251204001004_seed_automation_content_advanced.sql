-- =====================================================
-- 자동화 및 워크플로우 모듈 콘텐츠 - 중급/고급 레벨
-- =====================================================

-- ===== 중급 레벨 =====

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'overview', 'intermediate', '고급 워크플로우 패턴', 
'## 🎭 복잡한 비즈니스 프로세스 자동화

### 다단계 승인 워크플로우

```
신규 서버 요청 프로세스:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
요청 생성
    ↓
팀장 승인 (2일 이내)
    ↓ 승인            ↓ 거부
보안팀 검토               ↓
    ↓                 종료
예산팀 승인
    ↓
인프라팀 배정 → 서버 프로비저닝
    ↓
완료 및 인수인계
```

### 조건부 분기 워크플로우

```yaml
워크플로우: 장비 요청 처리
───────────────────────────
조건 분기:
  IF 요청 금액 < 100만원:
    → 팀장 승인만 필요
    → 자동 발주 시스템 연동
  
  ELSE IF 요청 금액 < 500만원:
    → 팀장 + 부서장 승인
    → 수동 발주 프로세스
  
  ELSE:
    → 팀장 + 부서장 + 재무팀 승인
    → CFO 최종 승인
    → 이사회 보고
```

### 병렬 처리 워크플로우

```
┌─────────────────────────────────────────┐
│       신입사원 온보딩 워크플로우          │
└─────────────────────────────────────────┘
                 │
         ┌───────┼───────┬────────┐
         ↓       ↓       ↓        ↓
    ┌────────┐ ┌────┐ ┌────┐ ┌────────┐
    │AD 계정 │ │이메일│ │Slack│ │장비 배정│
    │  생성  │ │ 설정 │ │초대 │ │        │
    └────────┘ └────┘ └────┘ └────────┘
         │       │       │        │
         └───────┴───────┴────────┘
                 │
                 ↓
         모든 작업 완료 대기
                 │
                 ↓
         환영 이메일 발송
```

> 💡 **팁**: 복잡한 워크플로우는 순서도로 먼저 그려보세요.', 1);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'core_concepts', 'intermediate', '조건 로직과 표현식', 
'## 🧮 고급 조건 설정

### 비교 연산자

| 연산자 | 의미 | 예시 |
|-------|------|------|
| `=` | 같음 | 우선순위 = "높음" |
| `!=` | 다름 | 상태 != "종료됨" |
| `>` | 초과 | 생성 후 경과 시간 > 24 |
| `<` | 미만 | SLA 잔여 시간 < 2 |
| `contains` | 포함 | 제목 contains "긴급" |
| `not contains` | 불포함 | 설명 not contains "해결" |

### 논리 연산자

```yaml
AND 조건 (모두 만족):
  우선순위 = "긴급"
  AND 상태 = "신규"
  AND 생성 시간 > 30분 전

OR 조건 (하나라도 만족):
  카테고리 = "서버 장애"
  OR 제목 contains "다운"
  OR 우선순위 = "긴급"

복합 조건:
  (카테고리 = "하드웨어" OR 카테고리 = "네트워크")
  AND 우선순위 = "긴급"
  AND 요청자 부서 = "영업팀"
```

### Liquid 템플릿 문법

```liquid
<!-- 조건부 텍스트 -->
{% if ticket.priority == ''Urgent'' %}
  ⚠️ 긴급 티켓입니다!
{% elsif ticket.priority == ''High'' %}
  ⬆️ 우선 처리가 필요합니다.
{% else %}
  일반 티켓입니다.
{% endif %}

<!-- 반복문 -->
{% for item in ticket.custom_fields.selected_items %}
  - {{ item }}
{% endfor %}

<!-- 날짜 포맷 -->
처리 기한: {{ ticket.due_by | date: "%Y년 %m월 %d일 %H:%M" }}

<!-- 조건부 이메일 -->
안녕하세요, 
{% if ticket.requester.first_name %}
  {{ ticket.requester.first_name }}님
{% else %}
  고객님
{% endif %}
```

### 시간 기반 조건

```yaml
예시 1: 업무 시간 체크
────────────────────
조건:
  현재 시간 between 09:00 and 18:00
  AND 요일 in [월, 화, 수, 목, 금]

예시 2: SLA 임박 체크
────────────────────
조건:
  SLA 잔여 시간 < 2시간
  AND 티켓 상태 != "해결됨"

예시 3: 장기 미해결
────────────────────
조건:
  생성일로부터 경과 > 5일
  AND 마지막 업데이트로부터 > 48시간
```

> 💡 **주의**: 조건이 복잡할수록 유지보수가 어렵습니다. 가능하면 단순하게 유지하세요.', 2);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'features', 'intermediate', 'Webhook과 외부 시스템 연동', 
'## 🔗 Webhook을 통한 시스템 통합

### Webhook이란?

**Webhook**은 이벤트 발생 시 외부 시스템에 HTTP 요청을 보내는 방법입니다.

### Webhook 활용 시나리오

| 시나리오 | 설명 |
|---------|------|
| **Slack 알림** | 긴급 티켓 생성 시 Slack 채널에 메시지 |
| **Jira 연동** | 버그 티켓 생성 시 Jira 이슈 자동 생성 |
| **모니터링 연동** | 인시던트 해결 시 모니터링 시스템 업데이트 |
| **커스텀 앱** | 자체 개발한 시스템에 데이터 전송 |

### Slack Webhook 예시

```yaml
워크플로우: 긴급 티켓 Slack 알림
──────────────────────────────
트리거: 티켓 생성됨

조건:
  우선순위 = "긴급"

액션: Webhook 호출
  URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  Method: POST
  Headers:
    Content-Type: application/json
  Body:
    {
      "text": "🚨 긴급 티켓 발생!",
      "blocks": [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "*티켓 #{{ticket.id}}*\n{{ticket.subject}}"
          }
        },
        {
          "type": "section",
          "fields": [
            {
              "type": "mrkdwn",
              "text": "*요청자:*\n{{ticket.requester.name}}"
            },
            {
              "type": "mrkdwn",
              "text": "*담당자:*\n{{ticket.agent.name}}"
            }
          ]
        },
        {
          "type": "actions",
          "elements": [
            {
              "type": "button",
              "text": {
                "type": "plain_text",
                "text": "티켓 보기"
              },
              "url": "https://yourcompany.freshservice.com/helpdesk/tickets/{{ticket.id}}"
            }
          ]
        }
      ]
    }
```

### API 인증 처리

```yaml
Basic Auth:
  Headers:
    Authorization: Basic base64(username:password)

Bearer Token:
  Headers:
    Authorization: Bearer YOUR_API_TOKEN

API Key:
  Headers:
    X-API-Key: YOUR_API_KEY
```

### 응답 처리 및 오류 대응

```yaml
성공 조건:
  HTTP 상태 코드: 200-299

재시도 정책:
  실패 시 재시도: 3회
  재시도 간격: 5분
  
오류 처리:
  IF 연속 3회 실패:
    → 관리자에게 이메일 알림
    → 워크플로우 일시 비활성화
```

> 💡 **보안 팁**: API 키나 비밀번호는 절대 워크플로우에 하드코딩하지 마세요. Freshservice의 보안 변수 기능을 사용하세요.', 3);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'practice', 'intermediate', '실전 워크플로우 구현', 
'## 🏗️ 실전 자동화 프로젝트

### 프로젝트 1: 퇴사자 계정 비활성화

**요구사항**: 퇴사 예정일 전날 자동으로 모든 접근권한 차단

```yaml
워크플로우: 퇴사자 오프보딩
──────────────────────────
트리거: 시간 기반 (매일 오전 8시)

조건:
  서비스 요청 유형 = "퇴사 처리"
  AND 상태 = "승인됨"
  AND 퇴사 예정일 = 내일

액션:
  1. Webhook → AD 계정 비활성화
     POST https://ad-api.company.com/users/{{user_id}}/disable
  
  2. Webhook → 이메일 계정 비활성화
     POST https://graph.microsoft.com/v1.0/users/{{user_id}}
     Body: {"accountEnabled": false}
  
  3. Webhook → VPN 접근 차단
     DELETE https://vpn-api.company.com/access/{{user_id}}
  
  4. 티켓 생성 → 장비 회수
     제목: "[긴급] {{퇴사자명}} 장비 회수 필요"
     그룹: IT자산관리팀
  
  5. 이메일 전송 → 관리자
     제목: "{{퇴사자명}} 계정 비활성화 완료"
```

### 프로젝트 2: 자동 에스컬레이션

**요구사항**: SLA 위반 임박 시 자동으로 상위 레벨 지원 팀에 전달

```yaml
워크플로우: SLA 기반 에스컬레이션
──────────────────────────────
트리거: 시간 기반 (30분마다 실행)

조건:
  SLA 위반까지 잔여 시간 < 1시간
  AND 상태 != "해결됨"
  AND 에스컬레이션 단계 = 0

액션 체인:
  1. 필드 업데이트
     - 에스컬레이션 단계 = 1
     - 우선순위 = "긴급"
  
  2. 그룹 재배정
     기존: Tier-1 Support
     신규: Tier-2 Support
  
  3. 담당자 배정
     방식: 부하 균등 (가장 적은 티켓 보유자)
  
  4. 이메일 전송 (담당자)
     제목: "⚠️ 에스컬레이션: SLA 위반 임박 #{{ticket.id}}"
  
  5. 이메일 전송 (관리자)
     제목: "SLA 위반 임박 티켓 현황"
  
  6. Slack 알림
     채널: #sla-alerts
```

### 프로젝트 3: 지식베이스 자동 제안

**요구사항**: 티켓 내용 분석해서 관련 KB 문서 자동 추천

```yaml
워크플로우: KB 자동 추천
──────────────────────
트리거: 티켓 생성됨

조건:
  채널 = "포털" (사용자 직접 생성)
  AND 카테고리 in [소프트웨어, 계정, 접근권한]

액션:
  1. API 호출 → KB 검색
     GET /api/v2/solutions/articles/search
     Query: {{ticket.subject}} {{ticket.description}}
  
  2. 조건부 분기
     IF 관련 문서 존재:
       → 이메일 발송 (요청자)
         제목: "해결에 도움이 될 만한 문서"
         본문:
           이 문서들이 도움이 될 수 있습니다:
           {% for article in search_results limit:3 %}
           - {{ article.title }}
             {{ article.url }}
           {% endfor %}
           
           해결되지 않으면 담당자가 곧 연락드리겠습니다.
     
     ELSE:
       → 즉시 담당자 배정
```

> 💡 **실전 팁**: 복잡한 워크플로우는 단계별로 테스트하세요. 한 번에 모든 액션을 추가하지 말고, 하나씩 검증하면서 추가하세요.', 4);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'faq', 'intermediate', '중급 FAQ', 
'## ❓ 중급 자동화 FAQ

### Q1: Webhook 호출이 실패해요

**디버깅 체크리스트**:
```
1. URL 확인
   □ 올바른 엔드포인트인가?
   □ HTTPS인가? (HTTP는 차단될 수 있음)

2. 인증 확인
   □ API 키가 유효한가?
   □ 권한이 충분한가?

3. 페이로드 확인
   □ JSON 형식이 올바른가?
   □ 필수 필드가 누락되지 않았나?

4. 실행 로그 확인
   Admin → Workflows → Execution Logs
   - 요청 본문
   - 응답 코드
   - 에러 메시지
```

---

### Q2: 워크플로우 실행 순서를 제어하려면?

**방법 1: 지연(Delay) 사용**
```yaml
액션1: 이메일 발송
↓
지연: 10분
↓
액션2: 상태 확인
```

**방법 2: 별도 워크플로우로 분리**
```yaml
워크플로우 A:
  액션: 티켓 필드 업데이트
  
워크플로우 B:
  트리거: 특정 필드 업데이트됨
  액션: 후속 처리
```

---

### Q3: 동일한 워크플로우가 여러 번 실행돼요

**원인과 해결**:

**원인 1**: 업데이트 이벤트가 반복 트리거
```yaml
# 나쁜 예
트리거: Ticket Updated
액션: 필드 업데이트 (무한 루프!)

# 좋은 예
트리거: Ticket Updated
조건: 특정 필드가 변경됨
액션: 다른 필드 업데이트
```

**원인 2**: 여러 워크플로우가 충돌
```yaml
해결책:
- 워크플로우 우선순위 설정
- 상호 배타적 조건 사용
- 실행 횟수 제한 (1회만)
```

---

### Q4: 복잡한 데이터 변환이 필요해요

**Liquid 필터 활용**:
```liquid
<!-- 대문자 변환 -->
{{ ticket.subject | upcase }}

<!-- 날짜 계산 -->
{% assign due_date = ''now'' | date: ''%s'' | plus: 259200 %}
{{ due_date | date: "%Y-%m-%d" }}

<!-- 배열 처리 -->
{% assign items = ticket.custom_fields.items | split: '','' %}
{% for item in items %}
  - {{ item | strip }}
{% endfor %}

<!-- 조건부 기본값 -->
{{ ticket.custom_fields.department | default: "미분류" }}
```

---

### Q5: 워크플로우 성능을 개선하려면?

**최적화 팁**:

1. **조건 최적화**
   - 가장 흔한 케이스를 먼저 체크
   - 불필요한 조건 제거

2. **API 호출 최소화**
   - 한 번 조회한 데이터는 변수에 저장
   - 배치 API 활용

3. **병렬 처리**
   - 독립적인 액션은 병렬로 실행
   - 의존성 있는 것만 순차 실행

4. **캐싱 활용**
   - 자주 참조하는 데이터는 커스텀 필드에 저장
   - API 조회 빈도 감소

> 💡 **모니터링**: 워크플로우 실행 로그를 정기적으로 검토하여 오류 패턴을 파악하세요.', 5);

-- ===== 고급 레벨 =====

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'overview', 'advanced', '엔터프라이즈 자동화 아키텍처', 
'## 🏛️ 대규모 자동화 시스템 설계

### 계층화된 자동화 구조

```
┌─────────────────────────────────────────────────────┐
│              Orchestration Layer                    │
│         (복잡한 비즈니스 프로세스)                    │
│   예: 신입사원 온보딩, 서버 프로비저닝                │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│            Automation Layer                         │
│         (재사용 가능한 자동화 블록)                   │
│   예: 계정 생성, 권한 부여, 알림 전송                 │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│            Integration Layer                        │
│          (외부 시스템 연동 API)                       │
│   예: AD, Office 365, AWS, Jira                     │
└─────────────────────────────────────────────────────┘
```

### 자동화 거버넌스 프레임워크

```yaml
자동화 라이프사이클:
  1. 제안 (Proposal)
     - 비즈니스 케이스 작성
     - ROI 계산
     - 리스크 평가
  
  2. 설계 (Design)
     - 워크플로우 다이어그램
     - 예외 시나리오 정의
     - 롤백 계획
  
  3. 개발 (Development)
     - 개발 환경에서 구현
     - 단위 테스트
     - 문서화
  
  4. 테스트 (Testing)
     - UAT (사용자 수용 테스트)
     - 부하 테스트
     - 보안 검토
  
  5. 배포 (Deployment)
     - 단계적 롤아웃
     - 모니터링 설정
     - 교육 실시
  
  6. 운영 (Operations)
     - 성능 모니터링
     - 정기 리뷰
     - 개선 사항 반영
```

### 멀티 테넌트 자동화

```
┌─────────────────────────────────────────┐
│        글로벌 워크플로우                  │
│    (모든 조직에 적용되는 기본 규칙)        │
└─────────────────────────────────────────┘
                 │
     ┌───────────┼───────────┐
     ↓           ↓           ↓
┌─────────┐ ┌─────────┐ ┌─────────┐
│  한국   │ │  미국   │ │  유럽   │
│ 로컬화  │ │ 로컬화  │ │ 로컬화  │
└─────────┘ └─────────┘ └─────────┘
  언어, 업무시간, 승인 프로세스 차이
```

> 💡 **핵심**: 대규모 조직에서는 자동화도 "코드"처럼 관리해야 합니다 - 버전 관리, 테스트, 문서화가 필수입니다.', 1);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'core_concepts', 'advanced', 'API 기반 고급 자동화', 
'## 🔧 Freshservice API를 활용한 자동화

### API 자동화 vs 워크플로우 오토메이터

| 구분 | 워크플로우 오토메이터 | API 자동화 |
|-----|-------------------|----------|
| **난이도** | 낮음 (GUI) | 높음 (코딩 필요) |
| **유연성** | 제한적 | 무제한 |
| **복잡도** | 단순~중간 | 복잡 가능 |
| **외부 시스템** | Webhook만 | 자유로운 연동 |

### Python으로 자동화 스크립트 작성

```python
import requests
from typing import List, Dict
import schedule
import time

class FreshserviceAutomation:
    def __init__(self, domain: str, api_key: str):
        self.base_url = f"https://{domain}.freshservice.com/api/v2"
        self.auth = (api_key, "X")
        self.headers = {"Content-Type": "application/json"}
    
    def get_overdue_tickets(self) -> List[Dict]:
        """SLA 위반 임박 티켓 조회"""
        response = requests.get(
            f"{self.base_url}/tickets",
            auth=self.auth,
            params={
                "filter": "overdue",
                "include": "requester,agent"
            }
        )
        return response.json().get("tickets", [])
    
    def escalate_ticket(self, ticket_id: int, group_id: int):
        """티켓 에스컬레이션"""
        response = requests.put(
            f"{self.base_url}/tickets/{ticket_id}",
            auth=self.auth,
            json={
                "group_id": group_id,
                "priority": 4,  # Urgent
                "tags": ["escalated", "sla-breach"]
            }
        )
        return response.json()
    
    def send_summary_email(self, tickets: List[Dict]):
        """관리자에게 요약 이메일"""
        # 이메일 발송 로직
        pass
    
    def auto_escalation_job(self):
        """정기 실행 작업: 자동 에스컬레이션"""
        print(f"[{time.strftime(''%Y-%m-%d %H:%M'')}] 에스컬레이션 체크 시작")
        
        overdue_tickets = self.get_overdue_tickets()
        escalated_count = 0
        
        for ticket in overdue_tickets:
            # 이미 에스컬레이션된 티켓은 스킵
            if "escalated" in ticket.get("tags", []):
                continue
            
            # Tier-2로 에스컬레이션
            self.escalate_ticket(
                ticket_id=ticket["id"],
                group_id=2000000123  # Tier-2 Support 그룹 ID
            )
            escalated_count += 1
        
        if escalated_count > 0:
            self.send_summary_email(overdue_tickets)
        
        print(f"에스컬레이션 완료: {escalated_count}건")

# 사용 예시
automation = FreshserviceAutomation("company", "YOUR_API_KEY")

# 30분마다 실행
schedule.every(30).minutes.do(automation.auto_escalation_job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 대량 작업 자동화

```python
def bulk_update_tickets(ticket_ids: List[int], updates: Dict):
    """여러 티켓 일괄 업데이트"""
    results = []
    
    for ticket_id in ticket_ids:
        try:
            response = requests.put(
                f"{base_url}/tickets/{ticket_id}",
                auth=auth,
                json=updates
            )
            results.append({
                "ticket_id": ticket_id,
                "status": "success",
                "response": response.json()
            })
        except Exception as e:
            results.append({
                "ticket_id": ticket_id,
                "status": "error",
                "error": str(e)
            })
        
        # Rate limiting 방지
        time.sleep(0.5)
    
    return results

# 예: 특정 카테고리의 모든 티켓 그룹 재배정
ticket_ids = [1001, 1002, 1003, ...]
updates = {
    "group_id": 2000000456,
    "tags": ["migrated"]
}
results = bulk_update_tickets(ticket_ids, updates)
```

> 💡 **API Rate Limiting**: Freshservice API는 분당 요청 수 제한이 있습니다. 대량 작업 시 적절한 딜레이를 추가하세요.', 2);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'features', 'advanced', '머신러닝과 예측 자동화', 
'## 🤖 AI/ML 기반 지능형 자동화

### Freshservice Freddy AI 활용

```yaml
Freddy AI 기능:
  1. 티켓 자동 분류
     - 과거 데이터 학습
     - 카테고리 자동 예측
     - 정확도: ~85%
  
  2. 우선순위 추천
     - 내용 분석
     - 긴급도 자동 판단
  
  3. 담당자 추천
     - 전문성 매칭
     - 업무량 고려
  
  4. 해결 방법 제안
     - 유사 티켓 검색
     - KB 문서 추천
```

### 커스텀 ML 모델 연동

```python
import openai
from typing import Dict

class AITicketAnalyzer:
    def __init__(self, openai_api_key: str):
        openai.api_key = openai_api_key
    
    def analyze_sentiment(self, ticket_text: str) -> Dict:
        """티켓 내용의 감정 분석"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "티켓 내용을 분석하여 고객의 감정 상태를 판단하세요. "
                               "결과는 positive/neutral/negative/urgent 중 하나입니다."
                },
                {
                    "role": "user",
                    "content": ticket_text
                }
            ]
        )
        
        sentiment = response.choices[0].message.content
        
        # 감정에 따른 우선순위 매핑
        priority_map = {
            "urgent": 4,      # 긴급
            "negative": 3,    # 높음
            "neutral": 2,     # 중간
            "positive": 1     # 낮음
        }
        
        return {
            "sentiment": sentiment,
            "suggested_priority": priority_map.get(sentiment, 2)
        }
    
    def suggest_solution(self, ticket_text: str) -> str:
        """해결 방법 제안"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "IT 헬프데스크 전문가로서 티켓 해결 방법을 제안하세요."
                },
                {
                    "role": "user",
                    "content": f"티켓 내용: {ticket_text}"
                }
            ]
        )
        
        return response.choices[0].message.content

# 워크플로우와 연동
analyzer = AITicketAnalyzer("YOUR_OPENAI_API_KEY")

# Webhook으로 티켓 정보 수신
@app.route("/analyze_ticket", methods=["POST"])
def analyze_ticket():
    ticket_data = request.json
    
    # AI 분석
    analysis = analyzer.analyze_sentiment(
        ticket_data["description"]
    )
    
    # Freshservice API로 우선순위 업데이트
    update_ticket_priority(
        ticket_id=ticket_data["id"],
        priority=analysis["suggested_priority"]
    )
    
    return {"status": "success"}
```

### 예측 유지보수 자동화

```python
def predict_hardware_failure():
    """CMDB 자산 데이터 분석하여 장애 예측"""
    
    # 자산 정보 수집
    assets = get_all_assets()
    
    predictions = []
    for asset in assets:
        # 사용 기간, 티켓 빈도, 상태 등 분석
        risk_score = calculate_risk_score(asset)
        
        if risk_score > 0.7:  # 70% 이상 위험도
            # 예방 유지보수 티켓 자동 생성
            create_preventive_maintenance_ticket(
                asset_id=asset["id"],
                risk_score=risk_score,
                recommended_action="교체 검토"
            )
            predictions.append(asset)
    
    return predictions
```

> 💡 **윤리적 고려사항**: AI 기반 자동화는 편향성을 유발할 수 있습니다. 정기적으로 결과를 검토하고 공정성을 확인하세요.', 3);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'practice', 'advanced', '자동화 모니터링과 최적화', 
'## 📊 자동화 성능 관리

### 핵심 지표 (KPI)

| 지표 | 목표 | 측정 방법 |
|-----|------|---------|
| **자동화율** | 70%+ | 자동 처리 티켓 / 전체 티켓 |
| **정확도** | 95%+ | 올바른 배정 / 전체 배정 |
| **실행 성공률** | 99%+ | 성공 / 전체 시도 |
| **평균 처리 시간 감소** | 50%+ | 자동화 전후 비교 |
| **ROI** | 300%+ | 절감 비용 / 투자 비용 |

### 모니터링 대시보드

```
┌─────────────────────────────────────────────────────┐
│          자동화 성능 대시보드 (실시간)                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  📈 금일 실행 현황                                    │
│  ├─ 총 실행: 1,247회                                │
│  ├─ 성공: 1,234회 (98.9%) ✅                         │
│  ├─ 실패: 13회 (1.1%) ⚠️                            │
│  └─ 평균 실행 시간: 2.3초                            │
│                                                     │
│  🎯 자동화별 성능                                     │
│  ┌───────────────────────────────────────────┐     │
│  │ 자동 배정      ████████████████ 98% (823건) │     │
│  │ 이메일 알림    ███████████████░ 97% (456건) │     │
│  │ SLA 에스컬레이션 ██████████████ 95% (123건) │     │
│  │ 자동 종료      ████████████████ 99% (89건)  │     │
│  └───────────────────────────────────────────┘     │
│                                                     │
│  ⚠️ 최근 오류 (5건)                                  │
│  1. Webhook 타임아웃 (Slack 알림) - 3건              │
│  2. API 권한 부족 (AD 계정 생성) - 2건               │
│                                                     │
│  💰 비용 절감 효과                                    │
│  └─ 금월 절감: 약 180 시간 (인건비 약 ₩4,500,000)    │
└─────────────────────────────────────────────────────┘
```

### 로그 분석 및 디버깅

```python
import pandas as pd
from datetime import datetime, timedelta

def analyze_automation_logs():
    """워크플로우 실행 로그 분석"""
    
    # 최근 30일 로그 조회
    logs = get_workflow_execution_logs(days=30)
    df = pd.DataFrame(logs)
    
    # 분석 1: 실패율이 높은 워크플로우
    failure_rate = df.groupby("workflow_name").agg({
        "status": lambda x: (x == "failed").sum() / len(x) * 100
    })
    high_failure = failure_rate[failure_rate["status"] > 5]
    
    print("⚠️ 실패율 5% 이상 워크플로우:")
    print(high_failure)
    
    # 분석 2: 실행 시간이 긴 워크플로우
    slow_workflows = df.groupby("workflow_name").agg({
        "execution_time_ms": "mean"
    }).sort_values(by="execution_time_ms", ascending=False).head(10)
    
    print("\n🐌 실행 시간 Top 10:")
    print(slow_workflows)
    
    # 분석 3: 시간대별 실행 패턴
    df["hour"] = pd.to_datetime(df["executed_at"]).dt.hour
    hourly_pattern = df.groupby("hour").size()
    
    print("\n📊 시간대별 실행 빈도:")
    print(hourly_pattern)
    
    return {
        "high_failure_workflows": high_failure,
        "slow_workflows": slow_workflows,
        "hourly_pattern": hourly_pattern
    }
```

### 최적화 전략

```yaml
최적화 체크리스트:
  성능 개선:
    □ 불필요한 API 호출 제거
    □ 조건 평가 순서 최적화 (빠른 것 먼저)
    □ 캐싱 활용
    □ 병렬 처리 가능한 액션 식별
  
  안정성 향상:
    □ 재시도 로직 추가
    □ 타임아웃 설정
    □ 에러 핸들링 강화
    □ 폴백(Fallback) 시나리오 준비
  
  유지보수성:
    □ 명확한 네이밍
    □ 주석/문서화
    □ 버전 관리
    □ 정기 리뷰 스케줄
```

### A/B 테스트

```python
def ab_test_automation():
    """두 가지 자동화 방식 비교"""
    
    # 그룹 A: 기존 방식
    # 그룹 B: 개선된 방식
    
    tickets_group_a = get_tickets(tag="ab-test-a")
    tickets_group_b = get_tickets(tag="ab-test-b")
    
    metrics_a = calculate_metrics(tickets_group_a)
    metrics_b = calculate_metrics(tickets_group_b)
    
    print("A/B 테스트 결과:")
    print(f"그룹 A - 평균 처리 시간: {metrics_a[''avg_resolution_time'']}")
    print(f"그룹 B - 평균 처리 시간: {metrics_b[''avg_resolution_time'']}")
    
    improvement = (
        (metrics_a["avg_resolution_time"] - metrics_b["avg_resolution_time"])
        / metrics_a["avg_resolution_time"] * 100
    )
    
    print(f"개선율: {improvement:.1f}%")
    
    if improvement > 10:
        print("✅ 그룹 B 방식 전체 적용 권장")
    else:
        print("⏸️ 추가 테스트 필요")
```

> 💡 **지속적 개선**: 자동화는 "한 번 만들고 끝"이 아닙니다. 정기적인 모니터링과 최적화가 필수입니다.', 4);

INSERT INTO module_contents (module_id, section_type, level, title_ko, content_md, display_order) VALUES
('025af628-dffb-48b0-8270-60c286699db7', 'faq', 'advanced', '고급 FAQ', 
'## ❓ 고급 자동화 FAQ

### Q1: 자동화가 비즈니스 리스크를 유발할 수 있나요?

**리스크와 완화 전략**:

| 리스크 | 완화 방법 |
|-------|---------|
| **잘못된 액션 실행** | • 중요 액션은 승인 단계 추가<br>• 테스트 환경에서 충분한 검증<br>• 롤백 계획 수립 |
| **시스템 장애 전파** | • 서킷 브레이커 패턴<br>• 폴백 메커니즘<br>• 의존성 최소화 |
| **보안 취약점** | • 최소 권한 원칙<br>• API 키 암호화<br>• 정기 보안 감사 |
| **컴플라이언스 위반** | • 감사 로그 기록<br>• 승인 추적<br>• 데이터 보호 규정 준수 |

---

### Q2: 자동화 ROI를 어떻게 측정하나요?

**ROI 계산 프레임워크**:

```python
def calculate_automation_roi():
    # 비용
    development_hours = 40  # 개발 시간
    hourly_rate = 50000  # 시간당 인건비
    development_cost = development_hours * hourly_rate
    
    maintenance_monthly = 100000  # 월간 유지보수 비용
    
    # 효과
    tickets_automated_monthly = 500
    time_saved_per_ticket = 5  # 분
    total_time_saved = tickets_automated_monthly * time_saved_per_ticket / 60  # 시간
    monthly_savings = total_time_saved * hourly_rate
    
    # ROI
    annual_savings = monthly_savings * 12
    annual_cost = maintenance_monthly * 12
    net_benefit = annual_savings - annual_cost - development_cost
    roi_percent = (net_benefit / development_cost) * 100
    
    payback_period = development_cost / monthly_savings  # 개월
    
    return {
        "development_cost": development_cost,
        "monthly_savings": monthly_savings,
        "annual_roi": roi_percent,
        "payback_months": payback_period
    }

# 예시 결과:
# 개발 비용: ₩2,000,000
# 월간 절감: ₩2,083,333
# ROI: 1,150% (첫 해)
# 투자 회수: 1개월
```

---

### Q3: 멀티 시스템 오케스트레이션의 실패를 어떻게 처리하나요?

**Saga 패턴 적용**:

```yaml
신입사원 온보딩 Saga:
  
  순방향 트랜잭션:
    1. AD 계정 생성 → 성공
    2. 이메일 생성 → 성공
    3. Slack 초대 → 실패! ❌
  
  보상 트랜잭션 (Rollback):
    1. Slack 초대 취소 (N/A)
    2. 이메일 계정 삭제 ✅
    3. AD 계정 삭제 ✅
  
  결과:
    - 모든 변경사항 롤백
    - 관리자에게 실패 알림
    - 수동 처리 티켓 생성
```

**구현 예시**:
```python
class SagaOrchestrator:
    def __init__(self):
        self.executed_actions = []
    
    def execute_with_compensation(self, actions):
        try:
            for action in actions:
                result = action["forward"]()
                self.executed_actions.append({
                    "action": action,
                    "result": result
                })
        except Exception as e:
            # 실패 시 보상 트랜잭션 실행
            self.rollback()
            raise
    
    def rollback(self):
        for executed in reversed(self.executed_actions):
            try:
                executed["action"]["compensate"]()
            except Exception as e:
                log_error(f"보상 실패: {e}")
```

---

### Q4: 자동화 문서화 베스트 프랙티스는?

**문서화 템플릿**:

```markdown
# 워크플로우: 서버 프로비저닝 자동화

## 개요
- **목적**: AWS EC2 인스턴스 자동 생성
- **오너**: 인프라팀
- **생성일**: 2024-01-15
- **마지막 수정**: 2024-03-10

## 비즈니스 컨텍스트
개발팀의 서버 요청이 월 50건 이상 발생하며, 
수동 프로비저닝에 평균 2시간 소요.

## 트리거 조건
- 서비스 항목: "개발 서버 요청"
- 상태: "승인됨"

## 워크플로우 단계
1. 사양 검증 (CPU, RAM, 스토리지)
2. AWS API 호출 - EC2 인스턴스 생성
3. 보안 그룹 설정
4. DNS 레코드 추가
5. Ansible로 기본 구성
6. 요청자에게 접속 정보 이메일

## 예외 처리
- AWS API 실패 → 15분 후 재시도 (최대 3회)
- 할당량 초과 → 관리자 승인 요청
- 보안 위반 → 자동 거부 및 보안팀 알림

## 의존성
- AWS CLI 인증 정보
- Ansible playbook: server_base_config.yml
- DNS 관리 API 접근 권한

## 모니터링
- 성공률 목표: 95%+
- 평균 실행 시간: < 10분
- 알림: 실패 시 #infra-alerts 채널

## 변경 이력
- 2024-03-10: 보안 그룹 템플릿 업데이트
- 2024-02-01: 재시도 로직 추가
- 2024-01-15: 최초 배포
```

---

### Q5: 자동화가 인간 에이전트의 일자리를 빼앗나요?

**재배치 전략**:

```
자동화로 대체되는 업무:
  - 반복적인 티켓 분류
  - 표준화된 서비스 요청 처리
  - 정기 알림 및 리마인더
  
↓

에이전트의 새로운 역할:
  - 복잡한 문제 해결 (L2/L3 지원)
  - 고객 경험 개선
  - 프로세스 최적화
  - 자동화 설계 및 개선
  - 예외 케이스 처리
```

**성공 사례**:
> "자동화 도입 후 Tier-1 업무 70% 감소했지만, 
> 팀원들은 더 복잡한 문제 해결과 프로젝트에 집중하게 되어 
> 직무 만족도가 30% 상승했습니다." - Fortune 500 IT 매니저

> 💡 **핵심**: 자동화는 사람을 대체하는 것이 아니라, 더 가치 있는 일을 할 수 있게 해줍니다.', 5);
