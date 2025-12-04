-- ============================================
-- 티켓 관리 기초 모듈 - 학습 콘텐츠 시드
-- 기초 → 중급 → 고급 단계별 학습
-- ============================================

-- 모듈 ID 변수 (티켓 관리 기초)
-- a720ffba-6e31-4436-a506-19ab68f43f52

-- ============================================
-- 기초 레벨 (Basic)
-- ============================================

-- 1. 개요
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'overview', 'basic', '티켓이란 무엇인가?', 'What is a Ticket?', 
$CONTENT$
## 🎫 티켓의 개념

**티켓(Ticket)**은 IT 서비스 데스크에서 사용자의 요청이나 문제를 추적하고 관리하기 위한 기록 단위입니다.

### 왜 티켓이 필요한가요?

| 티켓 없이 | 티켓 사용 시 |
|-----------|-------------|
| 요청이 누락될 수 있음 | 모든 요청이 기록됨 |
| 처리 상태 파악 어려움 | 실시간 상태 추적 가능 |
| 담당자 불명확 | 담당자 명확히 지정 |
| 히스토리 없음 | 전체 이력 보존 |

### 티켓의 주요 정보

```
📋 티켓 예시
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
티켓 번호: INC-2024-001234
제목: 이메일 로그인 불가
요청자: 김철수 (영업팀)
상태: 진행 중
우선순위: 높음
담당자: 박지원 (IT팀)
생성일: 2024-01-15 09:30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

> 💡 **핵심 포인트**: 티켓은 단순한 기록이 아니라, 서비스 품질을 측정하고 개선하는 데이터입니다.
$CONTENT$,
1, 5);

-- 2. 핵심 개념
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'core_concepts', 'basic', '티켓 생명주기', 'Ticket Lifecycle',
$CONTENT$
## 🔄 티켓 생명주기 (Lifecycle)

티켓은 생성부터 종료까지 여러 단계를 거칩니다.

### 기본 상태 흐름

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  신규   │ → │ 진행중  │ → │  해결   │ → │  종료   │
│  Open   │    │Progress │    │Resolved │    │ Closed  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     ↓              ↓              ↓
     └──────────────┴──────────────┘
              보류 (Pending)
```

### 각 상태의 의미

| 상태 | 설명 | 누가 변경? |
|------|------|-----------|
| **신규 (Open)** | 티켓이 막 생성됨, 아직 담당자 미배정 | 시스템/사용자 |
| **진행 중 (In Progress)** | 담당자가 작업 시작 | 에이전트 |
| **보류 (Pending)** | 추가 정보 대기 중 | 에이전트 |
| **해결 (Resolved)** | 문제 해결 완료, 사용자 확인 대기 | 에이전트 |
| **종료 (Closed)** | 완전히 처리 완료 | 시스템/사용자 |

### 🎯 실무 팁

1. **신규 → 진행 중**: 티켓을 받으면 즉시 상태 변경
2. **보류 사용 시**: 이유를 명확히 기록
3. **해결 후**: 사용자에게 확인 요청 메시지 전송

> ⚠️ **주의**: 티켓을 너무 오래 '신규' 상태로 두면 SLA 위반이 될 수 있습니다!
$CONTENT$,
2, 5);

-- 3. 우선순위와 긴급도
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'features', 'basic', '우선순위 설정하기', 'Setting Priority',
$CONTENT$
## ⚡ 우선순위 (Priority) 이해하기

### 우선순위 매트릭스

우선순위는 **영향도(Impact)**와 **긴급도(Urgency)**의 조합으로 결정됩니다.

```
              긴급도
         낮음    중간    높음
       ┌──────┬──────┬──────┐
  높음 │ 중간 │ 높음 │ 긴급 │
영     ├──────┼──────┼──────┤
향  중 │ 낮음 │ 중간 │ 높음 │
도     ├──────┼──────┼──────┤
  낮음 │ 낮음 │ 낮음 │ 중간 │
       └──────┴──────┴──────┘
```

### Freshservice 기본 우선순위

| 우선순위 | 응답 목표 | 해결 목표 | 예시 |
|---------|----------|----------|------|
| 🔴 **긴급 (Urgent)** | 15분 | 1시간 | 전사 시스템 장애 |
| 🟠 **높음 (High)** | 1시간 | 4시간 | 팀 단위 업무 불가 |
| 🟡 **중간 (Medium)** | 4시간 | 8시간 | 개인 업무 지장 |
| 🟢 **낮음 (Low)** | 8시간 | 24시간 | 문의, 개선 요청 |

### 🎯 우선순위 판단 체크리스트

□ 몇 명이 영향을 받는가?
□ 업무 중단이 발생하는가?
□ 대체 방법이 있는가?
□ 마감 기한이 있는가?

> 💡 **팁**: 사용자가 "긴급"이라고 해도 객관적으로 판단하세요. 모든 게 긴급이면 아무것도 긴급하지 않습니다!
$CONTENT$,
3, 5);

-- 4. 담당자 배정
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'practice', 'basic', '담당자 배정 방법', 'Agent Assignment',
$CONTENT$
## 👤 담당자 배정 (Assignment)

티켓을 적절한 담당자에게 배정하는 것은 빠른 해결의 핵심입니다.

### 배정 방법 3가지

#### 1️⃣ 수동 배정
```
티켓 상세 > 담당자 필드 > 에이전트 선택
```
- 장점: 정확한 전문가에게 배정 가능
- 단점: 시간 소요, 담당자 부하 불균형

#### 2️⃣ 라운드 로빈 (Round Robin)
```
A → B → C → A → B → C ...
```
- 장점: 균등한 업무 분배
- 단점: 전문성 고려 안 됨

#### 3️⃣ 부하 기반 (Load Balanced)
```
가장 적은 티켓을 가진 에이전트에게 자동 배정
```
- 장점: 현실적인 업무 분배
- 단점: 설정 필요

### 실습: 수동 배정하기

**Step 1**: 티켓 목록에서 티켓 클릭

**Step 2**: 우측 패널에서 '담당자' 필드 클릭

**Step 3**: 적절한 에이전트 선택

**Step 4**: 변경 저장

### 🎯 배정 시 고려사항

| 체크포인트 | 질문 |
|-----------|------|
| 전문성 | 이 문제를 해결할 수 있는가? |
| 가용성 | 현재 휴가/미팅 중은 아닌가? |
| 업무량 | 이미 티켓이 너무 많지 않은가? |
| 시간대 | 근무 시간인가? |

> 💡 **팁**: 자신이 해결할 수 없는 티켓은 빨리 다른 담당자에게 넘기세요!
$CONTENT$,
4, 5);

-- 5. FAQ
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'faq', 'basic', '자주 묻는 질문', 'FAQ',
$CONTENT$
## ❓ 자주 묻는 질문 (FAQ)

### Q1: 티켓을 잘못 생성했어요. 삭제할 수 있나요?

**A**: 일반적으로 티켓 삭제는 권장하지 않습니다. 대신:
- 상태를 '취소'로 변경
- 사유를 메모에 기록
- 관리자만 삭제 권한 보유

---

### Q2: 한 티켓에 여러 문제가 있으면 어떻게 하나요?

**A**: 문제별로 티켓을 분리하는 것이 좋습니다.
- **이유**: 각 문제의 상태와 담당자가 다를 수 있음
- **방법**: 하위 티켓(Child Ticket) 생성 또는 별도 티켓 생성 후 연결

---

### Q3: 사용자가 직접 티켓을 만들 수 있나요?

**A**: 네, 여러 방법이 있습니다.
- 🌐 셀프서비스 포털
- 📧 이메일 (support@회사.com)
- 💬 채팅 위젯
- 📞 전화 (에이전트가 대신 생성)

---

### Q4: 티켓이 너무 많아서 관리가 안 돼요!

**A**: 뷰(View)와 필터를 활용하세요.
```
내 티켓 > 상태: 진행중 > 우선순위: 높음
```
- 자주 쓰는 조건은 저장된 뷰로 만들기
- 대시보드에서 내 업무 현황 확인

---

### Q5: SLA가 뭔가요?

**A**: Service Level Agreement (서비스 수준 협약)
- 티켓 처리에 대한 시간 약속
- 예: "긴급 티켓은 1시간 내 해결"
- 위반 시 알림 발생 및 에스컬레이션
$CONTENT$,
5, 5);


-- ============================================
-- 중급 레벨 (Intermediate)
-- ============================================

-- 1. 티켓 분류 심화
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'overview', 'intermediate', 'ITIL 기반 티켓 분류', 'ITIL-based Ticket Classification',
$CONTENT$
## 📚 ITIL 프레임워크와 티켓 유형

### ITIL이란?

**ITIL (IT Infrastructure Library)**은 IT 서비스 관리의 국제 표준 프레임워크입니다.
Freshservice는 ITIL 베스트 프랙티스를 기반으로 설계되었습니다.

### 티켓 유형 (Ticket Types)

| 유형 | ITIL 용어 | 설명 | 예시 |
|------|----------|------|------|
| **인시던트** | Incident | 서비스 중단/저하 | 이메일 접속 불가 |
| **서비스 요청** | Service Request | 표준 서비스 요청 | 새 장비 신청 |
| **문제** | Problem | 인시던트의 근본 원인 | 서버 메모리 부족 |
| **변경** | Change | 인프라/서비스 변경 | 서버 업그레이드 |

### 인시던트 vs 서비스 요청

```
┌─────────────────────────────────────────────────────┐
│                    사용자 문의                        │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  서비스가 정상인가?  │
              └─────────────────────┘
                    │         │
                   YES        NO
                    │         │
                    ▼         ▼
            ┌───────────┐ ┌───────────┐
            │서비스 요청│ │ 인시던트  │
            └───────────┘ └───────────┘
```

### 🎯 올바른 분류의 중요성

1. **정확한 통계**: 어떤 유형의 문의가 많은지 파악
2. **적절한 프로세스**: 유형별 다른 워크플로우 적용
3. **SLA 적용**: 유형별 다른 응답/해결 시간
4. **리포팅**: 경영진 보고용 데이터

> 💡 **실무 팁**: 애매할 때는 '인시던트'로 시작하고, 분석 후 변경하세요.
$CONTENT$,
1, 7);

-- 2. SLA 심화
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'core_concepts', 'intermediate', 'SLA 정책 이해하기', 'Understanding SLA Policies',
$CONTENT$
## ⏱️ SLA (Service Level Agreement) 심화

### SLA 구성 요소

```
┌─────────────────────────────────────────────────────┐
│                    SLA 정책                          │
├─────────────────────────────────────────────────────┤
│  📍 대상: 긴급(Urgent) 우선순위 티켓                 │
│  ⏰ 첫 응답 시간: 15분                               │
│  ✅ 해결 시간: 1시간                                 │
│  📅 운영 시간: 24/7                                  │
│  🔔 에스컬레이션: 50%, 75%, 100%                     │
└─────────────────────────────────────────────────────┘
```

### SLA 타이머 작동 방식

| 이벤트 | 타이머 영향 |
|--------|------------|
| 티켓 생성 | 타이머 시작 ▶️ |
| 상태: 보류 | 타이머 일시정지 ⏸️ |
| 상태: 진행중 | 타이머 재개 ▶️ |
| 첫 응답 | 응답 타이머 종료 ⏹️ |
| 상태: 해결 | 해결 타이머 종료 ⏹️ |

### 에스컬레이션 단계

```
시간 경과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│         │              │              │
0%       50%            75%           100%
│         │              │              │
시작    Level 1       Level 2       Level 3
        (담당자)     (팀장)       (관리자)
        이메일        이메일        이메일+SMS
```

### 🎯 SLA 위반 방지 전략

1. **우선순위 정확히**: 과도한 긴급 티켓은 SLA 부담
2. **빠른 첫 응답**: "확인 중입니다" 라도 응답
3. **보류 활용**: 사용자 응답 대기 시 타이머 정지
4. **에스컬레이션 대응**: 알림 오면 즉시 조치

### SLA 보고서 주요 지표

| 지표 | 설명 | 목표 |
|------|------|------|
| SLA 준수율 | 기한 내 해결 비율 | > 95% |
| 평균 응답 시간 | 첫 응답까지 시간 | < 목표의 50% |
| 평균 해결 시간 | 해결까지 총 시간 | < 목표의 80% |

> ⚠️ **주의**: SLA는 계약이므로 위반 시 패널티가 있을 수 있습니다!
$CONTENT$,
2, 8);

-- 3. 티켓 필드 커스터마이징
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'features', 'intermediate', '커스텀 필드 활용', 'Custom Fields',
$CONTENT$
## 🔧 티켓 필드 커스터마이징

### 기본 제공 필드

Freshservice는 다음 필드를 기본 제공합니다:

- 제목, 설명, 상태, 우선순위
- 요청자, 담당자, 그룹
- 유형, 카테고리, 하위 카테고리
- 소스 (이메일, 포털, 전화 등)

### 커스텀 필드 추가하기

**설정 경로**: Admin > Form Fields > Ticket Fields

| 필드 유형 | 용도 | 예시 |
|----------|------|------|
| Text | 짧은 텍스트 | 자산 번호 |
| Paragraph | 긴 텍스트 | 상세 증상 |
| Dropdown | 선택형 | 영향받는 시스템 |
| Checkbox | 다중 선택 | 관련 서비스 |
| Date | 날짜 | 희망 완료일 |
| Number | 숫자 | 영향받는 사용자 수 |

### 실습: 드롭다운 필드 추가

```
1. Admin > Form Fields > Ticket Fields
2. "Add New Field" 클릭
3. 필드 유형: Dropdown 선택
4. 이름: "영향받는 부서" 입력
5. 옵션 추가:
   - 영업팀
   - 마케팅팀
   - 개발팀
   - 경영지원팀
6. 필수 여부 설정
7. 저장
```

### 조건부 필드 (Dependent Fields)

상위 선택에 따라 하위 옵션이 변경:

```
카테고리: 하드웨어
  └─ 하위 카테고리: 노트북, 모니터, 키보드...

카테고리: 소프트웨어  
  └─ 하위 카테고리: Office, 이메일, ERP...
```

### 🎯 필드 설계 베스트 프랙티스

✅ **DO**
- 필수 필드는 최소화 (5개 이하)
- 드롭다운 옵션은 명확하게
- 리포팅에 필요한 필드 우선

❌ **DON'T**
- 모든 필드를 필수로 설정
- 사용자에게 기술 용어 요구
- 너무 많은 필드 (10개 초과)
$CONTENT$,
3, 7);

-- 4. 티켓 뷰와 필터
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'practice', 'intermediate', '효율적인 뷰 관리', 'Efficient View Management',
$CONTENT$
## 👁️ 티켓 뷰(View)와 필터 마스터하기

### 뷰란?

**뷰(View)**는 특정 조건의 티켓만 보여주는 저장된 필터입니다.

### 기본 제공 뷰

| 뷰 이름 | 조건 |
|--------|------|
| 내 미해결 티켓 | 담당자=나, 상태≠종료 |
| 미배정 티켓 | 담당자=없음, 상태=신규 |
| 오늘 마감 | SLA 마감=오늘 |
| 긴급 티켓 | 우선순위=긴급 |

### 커스텀 뷰 만들기

**경로**: Tickets > Views > Create New View

```
뷰 이름: "VIP 고객 긴급 티켓"

조건:
  ┌─ 우선순위 = 긴급 OR 높음
  ├─ AND 요청자 그룹 = VIP
  ├─ AND 상태 ≠ 종료
  └─ AND 담당자 = 나

정렬: SLA 마감 시간 (오름차순)
표시 컬럼: 티켓번호, 제목, 요청자, SLA 상태
```

### 고급 필터 조건

| 조건 | 설명 | 예시 |
|------|------|------|
| is | 정확히 일치 | 상태 is "진행중" |
| is not | 제외 | 상태 is not "종료" |
| contains | 포함 | 제목 contains "긴급" |
| greater than | 초과 | 생성일 > 어제 |
| in | 목록 중 하나 | 우선순위 in (긴급, 높음) |

### 🎯 뷰 활용 베스트 프랙티스

1. **아침 점검 뷰**
   ```
   담당자=나 AND 상태=신규
   → 오늘 처리할 새 티켓 확인
   ```

2. **SLA 위험 뷰**
   ```
   SLA 상태=위험 OR SLA 상태=위반
   → 긴급 처리 필요 티켓
   ```

3. **주간 리뷰 뷰**
   ```
   담당자=나 AND 해결일=이번주
   → 이번 주 처리 완료 티켓
   ```

### 뷰 공유하기

- **개인 뷰**: 나만 사용
- **팀 뷰**: 그룹원 공유 (Admin 권한 필요)
- **전체 공개**: 모든 에이전트

> 💡 **팁**: 자주 쓰는 뷰는 즐겨찾기 ⭐ 해두세요!
$CONTENT$,
4, 6);


-- ============================================
-- 고급 레벨 (Advanced)
-- ============================================

-- 1. 자동화 심화
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'overview', 'advanced', '디스패처와 옵저버', 'Dispatcher and Observer',
$CONTENT$
## 🤖 티켓 자동화 심화

Freshservice의 자동화는 **디스패처(Dispatcher)**와 **옵저버(Observer)** 두 가지 방식으로 동작합니다.

### 디스패처 (Dispatcher) - 생성 시 자동화

티켓이 **생성될 때** 한 번 실행됩니다.

```
┌─────────────────────────────────────────────────────┐
│  🆕 티켓 생성                                        │
│         │                                           │
│         ▼                                           │
│  ┌─────────────────────────────────────────────┐    │
│  │           디스패처 규칙 평가                  │    │
│  │  IF 제목 contains "긴급"                     │    │
│  │  THEN 우선순위 = 높음                        │    │
│  │  AND 그룹 = Tier-2                          │    │
│  └─────────────────────────────────────────────┘    │
│         │                                           │
│         ▼                                           │
│  📋 티켓 저장 (수정된 속성 포함)                    │
└─────────────────────────────────────────────────────┘
```

**활용 예시**:
- 키워드 기반 우선순위 설정
- 이메일 도메인 기반 그룹 배정
- 카테고리 자동 분류

### 옵저버 (Observer) - 변경 시 자동화

티켓이 **업데이트될 때마다** 실행됩니다.

```
┌─────────────────────────────────────────────────────┐
│  📝 티켓 수정                                        │
│         │                                           │
│         ▼                                           │
│  ┌─────────────────────────────────────────────┐    │
│  │           옵저버 규칙 평가                    │    │
│  │  IF 상태 changed to "해결"                   │    │
│  │  THEN 이메일 전송 to 요청자                  │    │
│  │  AND 만족도 설문 전송                        │    │
│  └─────────────────────────────────────────────┘    │
│         │                                           │
│         ▼                                           │
│  📧 액션 실행                                       │
└─────────────────────────────────────────────────────┘
```

**활용 예시**:
- 상태 변경 시 알림 전송
- 우선순위 변경 시 에스컬레이션
- 3일 이상 보류 시 리마인더

### 디스패처 vs 옵저버 비교

| 항목 | 디스패처 | 옵저버 |
|------|---------|--------|
| 실행 시점 | 생성 시 1회 | 업데이트 시 매번 |
| 주 용도 | 초기 분류/라우팅 | 상태 변화 반응 |
| 조건 | 필드 값 기준 | 변경 이벤트 기준 |
| 성능 영향 | 낮음 | 중간 (복잡도에 따라) |

> 💡 **팁**: 디스패처로 초기 설정, 옵저버로 지속 관리하는 것이 베스트 프랙티스입니다.
$CONTENT$,
1, 8);

-- 2. 워크플로우 오토메이터
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'core_concepts', 'advanced', '워크플로우 오토메이터', 'Workflow Automator',
$CONTENT$
## ⚙️ 워크플로우 오토메이터 (Workflow Automator)

디스패처/옵저버보다 복잡한 비즈니스 로직을 구현할 수 있는 고급 자동화 도구입니다.

### 워크플로우 구성 요소

```
┌─────────────────────────────────────────────────────┐
│                  워크플로우                          │
├─────────────────────────────────────────────────────┤
│  🎯 트리거                                          │
│     └─ 티켓 생성됨                                  │
│                                                     │
│  🔍 조건                                            │
│     └─ IF 우선순위 = 긴급 AND 유형 = 인시던트      │
│                                                     │
│  ⚡ 액션들                                          │
│     ├─ 1. 그룹 배정: Tier-2                        │
│     ├─ 2. 이메일: 팀장 알림                        │
│     ├─ 3. 대기: 30분                               │
│     ├─ 4. 조건 체크: 담당자 배정됨?                │
│     │     ├─ Yes: 끝                               │
│     │     └─ No: 에스컬레이션                      │
│     └─ 5. 이메일: 관리자 알림                      │
└─────────────────────────────────────────────────────┘
```

### 고급 액션 유형

| 액션 | 설명 |
|------|------|
| **Wait** | 지정 시간 대기 |
| **Condition** | 분기 처리 |
| **Loop** | 반복 실행 |
| **Parallel** | 병렬 실행 |
| **Webhook** | 외부 시스템 호출 |
| **Custom Script** | JavaScript 코드 실행 |

### 실습: 긴급 티켓 에스컬레이션 워크플로우

```yaml
Trigger: Ticket Created
Conditions:
  - Priority equals "Urgent"

Actions:
  1. Set Field: Assign to "On-Call Agent"
  2. Send Email: Notify Team Lead
  3. Wait: 15 minutes
  4. Condition: Status is "Open"?
     - Yes:
       5. Send Email: Escalate to Manager
       6. Add Note: "Auto-escalated due to no response"
     - No:
       (End workflow)
```

### 워크플로우 디버깅

**실행 로그 확인**:
```
Admin > Workflow Automator > 워크플로우 선택 > Execution History
```

| 상태 | 의미 |
|------|------|
| ✅ Completed | 정상 완료 |
| ⏳ In Progress | 대기 중 (Wait 액션) |
| ❌ Failed | 오류 발생 |
| ⏸️ Paused | 수동 중지 |

> ⚠️ **주의**: 무한 루프를 만들지 않도록 조건을 신중하게 설계하세요!
$CONTENT$,
2, 10);

-- 3. API와 통합
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'features', 'advanced', 'API 활용하기', 'Using APIs',
$CONTENT$
## 🔌 Freshservice API 활용

### API 기본 개념

**REST API**를 통해 프로그래밍 방식으로 Freshservice를 제어할 수 있습니다.

### 인증 방법

```bash
# API Key 방식 (Base64 인코딩)
Authorization: Basic {base64(api_key:X)}

# 예시
curl -X GET "https://yourcompany.freshservice.com/api/v2/tickets" \
  -H "Authorization: Basic {YOUR_API_KEY_BASE64}" \
  -H "Content-Type: application/json"
```

### 주요 API 엔드포인트

| 작업 | Method | Endpoint |
|------|--------|----------|
| 티켓 목록 | GET | /api/v2/tickets |
| 티켓 상세 | GET | /api/v2/tickets/{id} |
| 티켓 생성 | POST | /api/v2/tickets |
| 티켓 수정 | PUT | /api/v2/tickets/{id} |
| 티켓 삭제 | DELETE | /api/v2/tickets/{id} |
| 메모 추가 | POST | /api/v2/tickets/{id}/notes |

### 티켓 생성 API 예시

```json
POST /api/v2/tickets
{
  "subject": "새 노트북 신청",
  "description": "신입사원 김철수 노트북이 필요합니다.",
  "email": "requester@company.com",
  "priority": 2,
  "status": 2,
  "type": "Service Request",
  "category": "Hardware",
  "sub_category": "Laptop"
}
```

### 응답 예시

```json
{
  "ticket": {
    "id": 12345,
    "subject": "새 노트북 신청",
    "status": 2,
    "priority": 2,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### 🎯 API 활용 사례

1. **모니터링 연동**: 장애 감지 시 자동 티켓 생성
2. **챗봇 연동**: Slack/Teams에서 티켓 생성
3. **리포팅**: 커스텀 대시보드 데이터 추출
4. **동기화**: HR 시스템과 사용자 정보 동기화

### Rate Limiting

```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705312800
```

- **한도**: 분당 50 요청 (플랜에 따라 다름)
- **초과 시**: 429 Too Many Requests
- **대응**: Retry-After 헤더 참고

> 💡 **팁**: 개발/테스트는 Sandbox 환경에서 하세요!
$CONTENT$,
3, 10);

-- 4. 성능 최적화
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'practice', 'advanced', '성능 최적화와 베스트 프랙티스', 'Performance Optimization',
$CONTENT$
## 🚀 티켓 관리 성능 최적화

### 대량 티켓 처리

#### 벌크 작업

```
Tickets > 체크박스로 선택 > Bulk Actions

가능한 작업:
- 상태 일괄 변경
- 담당자 일괄 배정
- 우선순위 일괄 변경
- 병합 (Merge)
- 삭제
```

#### 시나리오 자동화

**시나리오(Scenario)**는 자주 수행하는 작업 조합을 저장한 것입니다.

```yaml
시나리오 이름: "스팸 처리"
액션:
  1. 상태 변경: Closed
  2. 메모 추가: "스팸으로 분류됨"
  3. 태그 추가: spam
  4. 만족도 조사: 건너뛰기
```

### 팀 생산성 향상

#### 칸반 보드 활용

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│    신규     │   진행중    │    보류     │    해결     │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ [티켓-001] │ [티켓-003] │ [티켓-005] │ [티켓-007] │
│ [티켓-002] │ [티켓-004] │            │ [티켓-008] │
│            │            │            │ [티켓-009] │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

드래그 앤 드롭으로 상태 변경!

#### 키보드 단축키

| 단축키 | 기능 |
|-------|------|
| `j` / `k` | 티켓 목록 위/아래 이동 |
| `o` | 티켓 열기 |
| `r` | 답장 |
| `n` | 내부 메모 |
| `?` | 단축키 도움말 |

### 데이터 정리 (Housekeeping)

#### 정기 정리 체크리스트

- [ ] **매일**: 미배정 티켓 확인
- [ ] **매주**: 오래된 보류 티켓 검토
- [ ] **매월**: 오래된 종료 티켓 아카이브
- [ ] **분기**: 미사용 자동화 규칙 정리

#### 아카이브 정책

```
Admin > Ticket Settings > Archive Policy

조건: 종료 후 90일 경과
액션: Archive (읽기 전용)
```

### 🎯 성능 모니터링 지표

| 지표 | 측정 방법 | 목표 |
|------|----------|------|
| 평균 첫 응답 시간 | 리포트 > Response Time | < SLA 목표의 50% |
| 티켓 백로그 | 미해결 티켓 수 | 일정 수준 유지 |
| 일일 처리량 | 해결된 티켓/에이전트 | 10-20개 |
| 재오픈율 | 재오픈/전체 × 100 | < 5% |

> 💡 **마스터 팁**: 좋은 성능은 좋은 프로세스에서 나옵니다. 자동화할 수 있는 건 자동화하세요!
$CONTENT$,
4, 8);

-- 5. 트러블슈팅
INSERT INTO module_contents (module_id, section_type, level, title_ko, title_en, content_md, display_order, estimated_minutes) VALUES
('a720ffba-6e31-4436-a506-19ab68f43f52', 'faq', 'advanced', '고급 트러블슈팅', 'Advanced Troubleshooting',
$CONTENT$
## 🔧 고급 트러블슈팅 가이드

### 일반적인 문제와 해결법

#### 문제 1: SLA가 적용되지 않음

**증상**: 티켓에 SLA 타이머가 표시되지 않음

**해결 순서**:
1. SLA 정책 확인 (Admin > SLA Policies)
2. 정책 조건 확인 (우선순위, 유형 등)
3. 정책 적용 순서 확인
4. 운영 시간 설정 확인

```
디버깅:
Ticket > Ticket Details > View SLA Info
→ "No SLA policy applied" 표시 시 조건 불일치
```

---

#### 문제 2: 자동화 규칙이 동작하지 않음

**체크리스트**:
- [ ] 규칙이 활성화 상태인가?
- [ ] 조건이 올바른가? (AND/OR 주의)
- [ ] 규칙 순서가 맞는가?
- [ ] 다른 규칙과 충돌하지 않는가?

```
디버깅:
Admin > Automation > Activity Log
→ 규칙 실행 이력 확인
```

---

#### 문제 3: 이메일로 티켓이 생성되지 않음

**원인 분석**:
```
1. 이메일 수신 확인
   Admin > Email Settings > Incoming Logs

2. 스팸/차단 목록 확인
   Admin > Email Settings > Blocked Senders

3. 이메일 파싱 규칙 확인
   Admin > Email Settings > Email Commands

4. 이메일 서버 연결 확인
   Admin > Email Settings > Test Connection
```

---

### API 관련 문제

| 에러 코드 | 의미 | 해결 |
|----------|------|------|
| 401 | 인증 실패 | API 키 확인 |
| 403 | 권한 없음 | 에이전트 역할 확인 |
| 404 | 리소스 없음 | ID/URL 확인 |
| 429 | 요청 한도 초과 | 잠시 후 재시도 |
| 500 | 서버 오류 | 지원팀 문의 |

---

### 로그 분석

**감사 로그 (Audit Log)**:
```
Admin > Account > Audit Log

필터링 가능:
- 시간 범위
- 액션 유형 (Create, Update, Delete)
- 사용자
- 모듈 (Tickets, Users, etc.)
```

**주요 확인 포인트**:
- 누가 어떤 변경을 했는가?
- 자동화에 의한 변경인가?
- 삭제된 데이터 복구 가능한가?

---

### 🆘 지원 요청 시 포함할 정보

```markdown
## 문제 설명
[간단한 문제 요약]

## 재현 단계
1. ...
2. ...
3. ...

## 예상 동작
[어떻게 동작해야 하는지]

## 실제 동작
[실제로 어떻게 동작했는지]

## 환경 정보
- 도메인: yourcompany.freshservice.com
- 브라우저: Chrome 120
- 티켓 ID: #12345

## 스크린샷/로그
[첨부]
```

> 💡 **팁**: 문제 발생 시간을 정확히 기록해두면 로그 분석이 쉬워집니다!
$CONTENT$,
5, 7);

COMMIT;
