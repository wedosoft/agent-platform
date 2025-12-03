-- ============================================
-- Seed: Quiz Questions for Freshservice Core Modules
-- Date: 2025-12-03
-- Description: 60 quiz questions (3 modules × 20 questions each)
-- Each module has 10 basic + 10 advanced questions
-- ============================================

-- ============================================
-- 모듈 1: 티켓 관리 (Ticket Management)
-- Module ID: a1b2c3d4-0001-4000-8000-000000000001
-- ============================================

-- [기초] 티켓 관리 - 10 questions
INSERT INTO quiz_questions (module_id, difficulty, question, choices, correct_choice_id, explanation, question_order) VALUES

-- Q1
('a1b2c3d4-0001-4000-8000-000000000001', 'basic', 
'Freshservice에서 티켓의 우선순위(Priority)는 어떤 두 가지 요소의 조합으로 결정되나요?',

'[
    {"id": "a", "text": "영향도(Impact)와 긴급도(Urgency)"},
    {"id": "b", "text": "중요도(Importance)와 난이도(Difficulty)"},
    {"id": "c", "text": "카테고리(Category)와 상태(Status)"},
    {"id": "d", "text": "요청자(Requester)와 담당자(Agent)"}
]'::jsonb,
'a',
'우선순위는 Impact(영향 받는 사용자 수)와 Urgency(업무 긴급성)의 매트릭스로 자동 계산됩니다. 예: High Impact + High Urgent = Critical Priority',
1),

-- Q2
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓 생성 시 자동으로 적절한 담당자나 그룹에 할당하는 기능을 무엇이라고 하나요?',

'[
    {"id": "a", "text": "Auto Assignment Rules"},
    {"id": "b", "text": "Round Robin Assignment"},
    {"id": "c", "text": "Manual Routing"},
    {"id": "d", "text": "Smart Distribution"}
]'::jsonb,
'a',
'Assignment Rules를 설정하면 티켓 속성(카테고리, 우선순위 등)에 따라 자동으로 담당자/그룹에 할당됩니다.',
2),

-- Q3
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓 상태(Status) 중 일반적으로 사용되지 않는 것은?',

'[
    {"id": "a", "text": "Open"},
    {"id": "b", "text": "Pending"},
    {"id": "c", "text": "Resolved"},
    {"id": "d", "text": "Archived"}
]'::jsonb,
'd',
'Freshservice 기본 티켓 상태는 Open, Pending, Resolved, Closed입니다. Archived는 표준 상태가 아닙니다.',
3),

-- Q4
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓에 대한 고객의 응답을 기다리는 동안 사용하는 상태는?',

'[
    {"id": "a", "text": "Open"},
    {"id": "b", "text": "Pending"},
    {"id": "c", "text": "On Hold"},
    {"id": "d", "text": "Waiting"}
]'::jsonb,
'b',
'Pending 상태는 외부(고객)나 내부(다른 팀)의 응답을 기다릴 때 사용합니다. SLA 타이머도 일시 정지됩니다.',
4),

-- Q5
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓의 라이프사이클에서 일반적인 순서는?',

'[
    {"id": "a", "text": "Open → Pending → Resolved → Closed"},
    {"id": "b", "text": "New → Assigned → Resolved → Archived"},
    {"id": "c", "text": "Created → In Progress → Done → Deleted"},
    {"id": "d", "text": "Open → Closed → Pending → Resolved"}
]'::jsonb,
'a',
'표준 티켓 워크플로우: Open(접수) → Pending(대기, 선택적) → Resolved(해결) → Closed(완료)',
5),

-- Q6
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'한 명의 담당자가 티켓을 처리할 수 없어 다른 담당자나 그룹으로 옮기는 작업을 무엇이라 하나요?',

'[
    {"id": "a", "text": "Escalation"},
    {"id": "b", "text": "Reassignment"},
    {"id": "c", "text": "Transfer"},
    {"id": "d", "text": "Delegation"}
]'::jsonb,
'b',
'Reassignment는 티켓 담당자/그룹을 변경하는 것입니다. Escalation은 상위 레벨로 올리는 것을 의미합니다.',
6),

-- Q7
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓에 첨부할 수 있는 파일 형식 제한을 설정하는 주된 이유는?',

'[
    {"id": "a", "text": "보안 위협 방지"},
    {"id": "b", "text": "디스크 공간 절약"},
    {"id": "c", "text": "검색 속도 향상"},
    {"id": "d", "text": "UI 디자인 통일"}
]'::jsonb,
'a',
'실행 파일(.exe 등) 차단은 악성 코드 유입을 방지하기 위한 보안 조치입니다.',
7),

-- Q8
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'여러 티켓이 동일한 근본 원인을 가질 때, 하나의 주 티켓에 연결하는 기능은?',

'[
    {"id": "a", "text": "Merge Tickets"},
    {"id": "b", "text": "Parent-Child Tickets"},
    {"id": "c", "text": "Link Related Tickets"},
    {"id": "d", "text": "Group Tickets"}
]'::jsonb,
'b',
'Parent-Child 관계를 설정하여 하나의 근본 문제(Parent)에 여러 증상 티켓(Child)을 연결할 수 있습니다.',
8),

-- Q9
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓 필드 중 필수(Required) 필드로 설정하면 어떤 효과가 있나요?',

'[
    {"id": "a", "text": "해당 필드가 자동으로 채워짐"},
    {"id": "b", "text": "필드를 입력하지 않으면 티켓 생성 불가"},
    {"id": "c", "text": "필드가 더 크게 표시됨"},
    {"id": "d", "text": "필드에 기본값이 적용됨"}
]'::jsonb,
'b',
'Required 필드는 티켓 생성/업데이트 시 반드시 입력해야 하며, 비어있으면 저장이 차단됩니다.',
9),

-- Q10
('a1b2c3d4-0001-4000-8000-000000000001', 'basic',
'티켓 템플릿(Template)의 주요 용도는?',

'[
    {"id": "a", "text": "반복적인 티켓 생성 작업 간소화"},
    {"id": "b", "text": "티켓 디자인 변경"},
    {"id": "c", "text": "티켓 권한 관리"},
    {"id": "d", "text": "티켓 통계 생성"}
]'::jsonb,
'a',
'템플릿은 자주 발생하는 문의 유형에 대해 미리 정의된 제목, 설명, 카테고리 등을 재사용할 수 있게 합니다.',
10),

-- [심화] 티켓 관리 - 10 questions
-- Q11
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Automation Rule에서 "Ticket is created and Priority is High" 조건으로 "Send email to Manager" 액션을 설정했을 때, 이메일이 발송되는 시점은?',

'[
    {"id": "a", "text": "티켓 생성 직후 즉시"},
    {"id": "b", "text": "티켓이 Resolved 상태가 될 때"},
    {"id": "c", "text": "우선순위가 High로 변경될 때마다"},
    {"id": "d", "text": "티켓 생성 시 우선순위가 High인 경우에만"}
]'::jsonb,
'd',
'"Ticket is created" 이벤트는 생성 시점에만 트리거됩니다. 이후 우선순위 변경은 별도 Automation이 필요합니다.',
11),

-- Q12
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Observer 역할을 가진 사용자가 티켓에서 할 수 있는 작업은?',

'[
    {"id": "a", "text": "티켓 내용 조회만 가능"},
    {"id": "b", "text": "코멘트 추가 가능하지만 티켓 수정 불가"},
    {"id": "c", "text": "티켓 상태 변경 가능"},
    {"id": "d", "text": "티켓 삭제 가능"}
]'::jsonb,
'b',
'Observer는 티켓을 모니터링하고 댓글을 추가할 수 있지만, 티켓 필드(상태, 우선순위 등)는 수정할 수 없습니다.',
12),

-- Q13
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Canned Response(사전 정의 답변)의 가장 효과적인 활용 시나리오는?',

'[
    {"id": "a", "text": "모든 티켓에 동일한 인사말 자동 추가"},
    {"id": "b", "text": "FAQ처럼 자주 묻는 질문에 대한 표준 답변 제공"},
    {"id": "c", "text": "티켓 자동 종료"},
    {"id": "d", "text": "첨부파일 자동 다운로드"}
]'::jsonb,
'b',
'Canned Response는 비밀번호 재설정, VPN 설정 등 반복되는 문의에 대해 일관된 품질의 답변을 신속하게 제공합니다.',
13),

-- Q14
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Time Entry(작업 시간 기록) 기능을 사용하는 주된 목적은?',

'[
    {"id": "a", "text": "에이전트의 근무 시간 추적"},
    {"id": "b", "text": "티켓 해결에 소요된 실제 작업 시간 측정 및 빌링"},
    {"id": "c", "text": "SLA 타이머 조정"},
    {"id": "d", "text": "티켓 자동 종료"}
]'::jsonb,
'b',
'Time Entry는 티켓별 실제 작업 시간을 기록하여 생산성 분석, 리소스 계획, 고객 청구 등에 활용됩니다.',
14),

-- Q15
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Supervisor Rule의 주요 목적은?',

'[
    {"id": "a", "text": "티켓 생성 자동화"},
    {"id": "b", "text": "특정 조건의 티켓을 정기적으로 검색하여 일괄 처리"},
    {"id": "c", "text": "담당자 권한 관리"},
    {"id": "d", "text": "이메일 템플릿 생성"}
]'::jsonb,
'b',
'Supervisor는 정해진 시간마다 실행되어 조건에 맞는 티켓들을 찾아 자동 액션(할당, 상태변경 등)을 수행합니다.',
15),

-- Q16
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Collision Detection(충돌 감지) 기능이 필요한 상황은?',

'[
    {"id": "a", "text": "두 명의 담당자가 동시에 같은 티켓을 수정하려 할 때"},
    {"id": "b", "text": "중복 티켓이 생성될 때"},
    {"id": "c", "text": "SLA가 위반될 때"},
    {"id": "d", "text": "첨부파일 용량이 클 때"}
]'::jsonb,
'a',
'Collision Detection은 여러 담당자가 동시에 티켓을 편집할 때 변경사항 충돌을 방지하고 경고합니다.',
16),

-- Q17
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Workflow Automator에서 "Wait for" 조건을 사용하는 이유는?',

'[
    {"id": "a", "text": "서버 부하 분산"},
    {"id": "b", "text": "특정 시간 경과 또는 조건 충족 시까지 다음 액션 지연"},
    {"id": "c", "text": "담당자 승인 대기"},
    {"id": "d", "text": "티켓 백업"}
]'::jsonb,
'b',
'Wait 조건은 시간 지연(예: 24시간 후) 또는 상태 변경 등의 조건을 기다린 후 다음 액션을 실행합니다.',
17),

-- Q18
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Agent Collision이 발생했을 때 Freshservice의 기본 동작은?',

'[
    {"id": "a", "text": "먼저 저장하는 사람의 변경사항만 적용"},
    {"id": "b", "text": "나중에 저장하는 사람에게 경고 표시 후 덮어쓸지 선택"},
    {"id": "c", "text": "두 변경사항 자동 병합"},
    {"id": "d", "text": "티켓 잠금"}
]'::jsonb,
'b',
'나중에 저장하려는 담당자에게 "다른 담당자가 이미 수정함" 경고를 표시하고, 덮어쓸지 취소할지 선택하게 합니다.',
18),

-- Q19
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'CSAT(Customer Satisfaction) 설문을 자동으로 발송하기 위한 가장 적절한 트리거는?',

'[
    {"id": "a", "text": "티켓이 Open 상태로 생성될 때"},
    {"id": "b", "text": "티켓이 Resolved 또는 Closed 상태로 변경될 때"},
    {"id": "c", "text": "티켓이 Pending 상태일 때"},
    {"id": "d", "text": "담당자가 변경될 때"}
]'::jsonb,
'b',
'CSAT 설문은 일반적으로 티켓이 해결(Resolved) 또는 완료(Closed)되었을 때 고객에게 발송됩니다.',
19),

-- Q20
('a1b2c3d4-0001-4000-8000-000000000001', 'advanced',
'Ticket Merge 기능 사용 시 주의사항은?',

'[
    {"id": "a", "text": "병합 후 원본 티켓들은 자동 삭제됨"},
    {"id": "b", "text": "병합된 티켓의 모든 대화, 첨부파일, 시간 기록이 하나의 티켓으로 통합됨"},
    {"id": "c", "text": "병합은 되돌릴 수 있음"},
    {"id": "d", "text": "서로 다른 Requester의 티켓은 병합 불가"}
]'::jsonb,
'b',
'Merge는 여러 티켓의 모든 내용을 하나로 합치며, 이 작업은 되돌릴 수 없으므로 신중해야 합니다.',
20);

-- ============================================
-- 모듈 2: 서비스 카탈로그 (Service Catalog)
-- Module ID: a1b2c3d4-0002-4000-8000-000000000002
-- ============================================

-- [기초] 서비스 카탈로그 - 10 questions
INSERT INTO quiz_questions (module_id, difficulty, question, choices, correct_choice_id, explanation, question_order) VALUES

-- Q21
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Catalog의 주요 목적은?',

'[
    {"id": "a", "text": "사용자가 IT 서비스를 셀프서비스로 요청할 수 있는 포털 제공"},
    {"id": "b", "text": "티켓 자동 종료"},
    {"id": "c", "text": "담당자 일정 관리"},
    {"id": "d", "text": "자산 재고 관리"}
]'::jsonb,
'a',
'Service Catalog은 사용자에게 표준화된 IT 서비스 메뉴를 제공하여 쉽게 요청할 수 있게 하는 셀프서비스 포털입니다.',
21),

-- Q22
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Item(서비스 항목)을 생성할 때 반드시 설정해야 하는 것은?',

'[
    {"id": "a", "text": "가격 정보"},
    {"id": "b", "text": "서비스 이름과 카테고리"},
    {"id": "c", "text": "SLA 정책"},
    {"id": "d", "text": "이미지 아이콘"}
]'::jsonb,
'b',
'서비스 항목의 필수 정보는 이름과 카테고리입니다. 가격, SLA, 아이콘은 선택사항입니다.',
22),

-- Q23
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Request와 Incident의 차이는?',

'[
    {"id": "a", "text": "Service Request는 새로운 것 요청, Incident는 문제 해결 요청"},
    {"id": "b", "text": "Service Request는 유료, Incident는 무료"},
    {"id": "c", "text": "Service Request는 자동, Incident는 수동"},
    {"id": "d", "text": "차이 없음"}
]'::jsonb,
'a',
'Service Request는 신규 서비스/액세스 요청(예: 소프트웨어 설치), Incident는 정상 서비스가 중단된 문제(예: 로그인 안됨)입니다.',
23),

-- Q24
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Catalog에서 사용자에게 추가 정보를 입력받기 위해 사용하는 기능은?',

'[
    {"id": "a", "text": "Custom Forms"},
    {"id": "b", "text": "Survey"},
    {"id": "c", "text": "Dashboard"},
    {"id": "d", "text": "Webhook"}
]'::jsonb,
'a',
'Custom Forms를 통해 서비스 요청 시 필요한 정보(예: 소프트웨어 버전, 설치 날짜 등)를 동적으로 수집할 수 있습니다.',
24),

-- Q25
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Approval Workflow(승인 워크플로우)가 필요한 대표적인 서비스 요청은?',

'[
    {"id": "a", "text": "비밀번호 재설정"},
    {"id": "b", "text": "고가의 소프트웨어 라이선스 요청"},
    {"id": "c", "text": "FAQ 조회"},
    {"id": "d", "text": "사무용품 신청"}
]'::jsonb,
'b',
'고가 라이선스, 하드웨어 구매 등 비용이나 보안이 중요한 요청은 관리자/예산 담당자의 승인이 필요합니다.',
25),

-- Q26
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Catalog Category(카테고리)의 역할은?',

'[
    {"id": "a", "text": "서비스 항목을 논리적으로 그룹화하여 찾기 쉽게 함"},
    {"id": "b", "text": "티켓 자동 할당"},
    {"id": "c", "text": "가격 책정"},
    {"id": "d", "text": "SLA 적용"}
]'::jsonb,
'a',
'카테고리는 서비스를 "하드웨어", "소프트웨어", "액세스 권한" 등으로 분류하여 사용자가 쉽게 찾을 수 있게 합니다.',
26),

-- Q27
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'서비스 카탈로그에서 특정 사용자 그룹만 볼 수 있는 서비스를 설정하는 기능은?',

'[
    {"id": "a", "text": "Visibility Settings"},
    {"id": "b", "text": "Encryption"},
    {"id": "c", "text": "Firewall Rules"},
    {"id": "d", "text": "IP Whitelist"}
]'::jsonb,
'a',
'Visibility 설정으로 특정 부서나 역할에게만 서비스 항목을 표시할 수 있습니다(예: 개발자 전용 서비스).',
27),

-- Q28
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Fulfillment(이행) 프로세스란?',

'[
    {"id": "a", "text": "서비스 요청이 승인된 후 실제로 서비스를 제공하는 과정"},
    {"id": "b", "text": "티켓을 종료하는 과정"},
    {"id": "c", "text": "사용자 인증 과정"},
    {"id": "d", "text": "결제 처리"}
]'::jsonb,
'a',
'Fulfillment는 승인 후 실제 작업(소프트웨어 설치, 계정 생성 등)을 수행하여 서비스를 제공하는 단계입니다.',
28),

-- Q29
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Item의 "Delivery Time"은 무엇을 의미하나요?',

'[
    {"id": "a", "text": "서비스 요청부터 완료까지 예상 소요 시간"},
    {"id": "b", "text": "담당자 응답 시간"},
    {"id": "c", "text": "이메일 발송 시간"},
    {"id": "d", "text": "서버 업타임"}
]'::jsonb,
'a',
'Delivery Time은 사용자에게 "이 서비스는 약 2영업일 소요"와 같은 기대치를 제공하는 예상 완료 시간입니다.',
29),

-- Q30
('a1b2c3d4-0002-4000-8000-000000000002', 'basic',
'Service Catalog에서 자주 묻는 질문에 대한 답변을 제공하는 영역은?',

'[
    {"id": "a", "text": "Knowledge Base Articles"},
    {"id": "b", "text": "Dashboard"},
    {"id": "c", "text": "Reports"},
    {"id": "d", "text": "Audit Log"}
]'::jsonb,
'a',
'각 서비스 항목에 관련 KB 문서를 연결하여 사용자가 셀프서비스로 해결할 수 있도록 지원합니다.',
30),

-- [심화] 서비스 카탈로그 - 10 questions
-- Q31
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Multi-level Approval(다단계 승인)을 설정할 때 "Any" vs "All" 옵션의 차이는?',

'[
    {"id": "a", "text": "Any는 승인자 중 한 명만 승인하면 됨, All은 모든 승인자가 승인해야 함"},
    {"id": "b", "text": "Any는 자동 승인, All은 수동 승인"},
    {"id": "c", "text": "Any는 병렬 처리, All은 순차 처리"},
    {"id": "d", "text": "차이 없음"}
]'::jsonb,
'a',
'Any는 여러 승인자 중 1명만 승인해도 통과, All은 모든 지정된 승인자가 승인해야 다음 단계로 진행됩니다.',
31),

-- Q32
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Request Automation에서 "Auto-assign based on location" 규칙을 설정하는 이유는?',

'[
    {"id": "a", "text": "요청자의 지역 사무소에 있는 담당자에게 자동 할당"},
    {"id": "b", "text": "서버 위치 선택"},
    {"id": "c", "text": "배송지 자동 입력"},
    {"id": "d", "text": "시간대 변환"}
]'::jsonb,
'a',
'지역별 IT 팀이 있을 때, 서울 사용자는 서울 IT팀에, 부산 사용자는 부산 IT팀에 자동 할당하여 효율을 높입니다.',
32),

-- Q33
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Item에서 "Dependent Fields" 기능의 활용 예시는?',

'[
    {"id": "a", "text": "OS 선택 시 해당 OS에서 사용 가능한 소프트웨어만 다음 필드에 표시"},
    {"id": "b", "text": "필드 자동 저장"},
    {"id": "c", "text": "필드 암호화"},
    {"id": "d", "text": "필드 삭제"}
]'::jsonb,
'a',
'Dependent Field는 이전 선택에 따라 다음 필드 옵션이 동적으로 변경됩니다(예: Windows 선택 → MS Office 표시)',
33),

-- Q34
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Catalog의 "Cost Center" 필드를 활용하는 목적은?',

'[
    {"id": "a", "text": "IT 비용을 부서별로 추적하고 배분하기 위함(Chargeback)"},
    {"id": "b", "text": "결제 수단 선택"},
    {"id": "c", "text": "할인 쿠폰 적용"},
    {"id": "d", "text": "세금 계산"}
]'::jsonb,
'a',
'Cost Center는 IT 서비스 비용을 요청 부서에 청구(Chargeback)하거나, 부서별 IT 지출을 추적하는 데 사용됩니다.',
34),

-- Q35
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Recurring Service Request(반복 서비스 요청) 기능이 유용한 시나리오는?',

'[
    {"id": "a", "text": "매월 정기 보고서 생성 요청"},
    {"id": "b", "text": "일회성 비밀번호 재설정"},
    {"id": "c", "text": "긴급 장애 티켓"},
    {"id": "d", "text": "임시 문의"}
]'::jsonb,
'a',
'매월 백업 보고서, 분기별 라이선스 갱신 등 정기적으로 발생하는 요청을 자동으로 생성할 수 있습니다.',
35),

-- Q36
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Catalog에서 "Quantity" 필드를 설정하는 이유는?',

'[
    {"id": "a", "text": "한 번에 여러 개 요청 가능(예: 마우스 5개)"},
    {"id": "b", "text": "우선순위 설정"},
    {"id": "c", "text": "파일 크기 제한"},
    {"id": "d", "text": "담당자 수 조정"}
]'::jsonb,
'a',
'Quantity를 활성화하면 사용자가 동일 서비스를 여러 개 요청할 수 있고, 각 수량별 비용도 자동 계산됩니다.',
36),

-- Q37
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Item의 "Display to groups" 설정으로 달성할 수 있는 것은?',

'[
    {"id": "a", "text": "특정 그룹(부서)에만 서비스 노출"},
    {"id": "b", "text": "그룹 채팅 생성"},
    {"id": "c", "text": "그룹 이메일 발송"},
    {"id": "d", "text": "그룹별 할인 적용"}
]'::jsonb,
'a',
'예를 들어 "개발 서버 액세스"는 개발팀에만, "디자인 도구"는 디자인팀에만 표시하여 혼란을 줄입니다.',
37),

-- Q38
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Approval Workflow에서 "Auto-reject if not approved within X hours" 설정의 목적은?',

'[
    {"id": "a", "text": "승인자가 기한 내 응답하지 않으면 자동 거부하여 프로세스 지연 방지"},
    {"id": "b", "text": "비용 절감"},
    {"id": "c", "text": "보안 강화"},
    {"id": "d", "text": "이메일 스팸 방지"}
]'::jsonb,
'a',
'승인 대기로 요청이 무한정 지연되는 것을 방지하고, 일정 시간 후 자동 거부 또는 에스컬레이션합니다.',
38),

-- Q39
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Catalog Analytics에서 추적해야 할 핵심 지표가 아닌 것은?',

'[
    {"id": "a", "text": "가장 많이 요청되는 서비스 Top 10"},
    {"id": "b", "text": "평균 승인 소요 시간"},
    {"id": "c", "text": "서비스별 완료율"},
    {"id": "d", "text": "담당자의 점심 시간"}
]'::jsonb,
'd',
'Service Catalog KPI는 요청 건수, 승인 시간, 완료율, 사용자 만족도 등이며, 담당자 개인 일정은 무관합니다.',
39),

-- Q40
('a1b2c3d4-0002-4000-8000-000000000002', 'advanced',
'Service Bundle(서비스 번들)의 활용 사례는?',

'[
    {"id": "a", "text": "신입사원 온보딩 시 노트북+이메일+VPN을 한 번에 요청"},
    {"id": "b", "text": "티켓 자동 병합"},
    {"id": "c", "text": "파일 압축"},
    {"id": "d", "text": "대시보드 통합"}
]'::jsonb,
'a',
'Bundle은 여러 서비스를 하나의 패키지로 묶어 한 번에 요청할 수 있게 하여, 반복 작업을 줄입니다.',
40);

-- ============================================
-- 모듈 3: SLA 관리 (SLA Management)
-- Module ID: a1b2c3d4-0003-4000-8000-000000000003
-- ============================================

-- [기초] SLA 관리 - 10 questions
INSERT INTO quiz_questions (module_id, difficulty, question, choices, correct_choice_id, explanation, question_order) VALUES

-- Q41
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA는 무엇의 약자인가요?',

'[
    {"id": "a", "text": "Service Level Agreement"},
    {"id": "b", "text": "System Log Analysis"},
    {"id": "c", "text": "Secure Login Access"},
    {"id": "d", "text": "Software License Activation"}
]'::jsonb,
'a',
'SLA(Service Level Agreement)는 IT 서비스 제공자와 고객 간의 서비스 품질 약속입니다.',
41),

-- Q42
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA Policy에서 일반적으로 정의하는 두 가지 주요 시간 지표는?',

'[
    {"id": "a", "text": "First Response Time과 Resolution Time"},
    {"id": "b", "text": "Login Time과 Logout Time"},
    {"id": "c", "text": "Upload Time과 Download Time"},
    {"id": "d", "text": "Start Time과 End Time"}
]'::jsonb,
'a',
'First Response Time(최초 응답 시간)과 Resolution Time(해결 시간)이 SLA의 핵심 지표입니다.',
42),

-- Q43
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA 위반(Violation)이 발생하는 경우는?',

'[
    {"id": "a", "text": "정해진 시간 내에 응답하지 못했을 때"},
    {"id": "b", "text": "티켓을 생성했을 때"},
    {"id": "c", "text": "사용자가 로그인했을 때"},
    {"id": "d", "text": "담당자가 변경되었을 때"}
]'::jsonb,
'a',
'SLA에서 약속한 응답 또는 해결 시간을 초과하면 Violation(위반)으로 기록되고, 에스컬레이션이 트리거됩니다.',
43),

-- Q44
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'Business Hours(업무 시간)를 SLA에 설정하는 이유는?',

'[
    {"id": "a", "text": "SLA 타이머가 업무 시간에만 동작하도록 하기 위함"},
    {"id": "b", "text": "담당자 출퇴근 기록"},
    {"id": "c", "text": "급여 계산"},
    {"id": "d", "text": "서버 점검 스케줄"}
]'::jsonb,
'a',
'예를 들어 평일 9-18시만 업무시간이면, 금요일 17시에 접수된 4시간 SLA 티켓은 다음주 월요일 11시에 만료됩니다.',
44),

-- Q45
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA Escalation(에스컬레이션)의 목적은?',

'[
    {"id": "a", "text": "SLA 위반 전에 상위 관리자에게 알림을 보내 조치를 유도"},
    {"id": "b", "text": "티켓 자동 종료"},
    {"id": "c", "text": "비용 청구"},
    {"id": "d", "text": "파일 백업"}
]'::jsonb,
'a',
'Escalation은 SLA 만료 전 일정 시간(예: 80%)에 관리자에게 알려 사전 대응할 수 있게 합니다.',
45),

-- Q46
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA가 "Pending" 상태의 티켓에 적용되는 방식은?',

'[
    {"id": "a", "text": "SLA 타이머가 일시 정지됨"},
    {"id": "b", "text": "SLA 타이머가 2배 빠르게 진행됨"},
    {"id": "c", "text": "SLA가 자동 연장됨"},
    {"id": "d", "text": "SLA가 리셋됨"}
]'::jsonb,
'a',
'Pending(외부 응답 대기) 상태에서는 SLA 타이머가 멈추고, 티켓이 다시 Open되면 남은 시간부터 재개됩니다.',
46),

-- Q47
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA Targets을 Priority별로 다르게 설정하는 이유는?',

'[
    {"id": "a", "text": "중요한 티켓은 더 빠르게 응답/해결해야 하므로"},
    {"id": "b", "text": "모든 티켓을 동일하게 처리하기 위해"},
    {"id": "c", "text": "담당자 성과 평가"},
    {"id": "d", "text": "서버 부하 분산"}
]'::jsonb,
'a',
'Critical 티켓은 1시간 내 응답, Low 티켓은 24시간 내 응답 등 우선순위에 따라 차등 SLA를 적용합니다.',
47),

-- Q48
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA Compliance Rate(준수율)이란?',

'[
    {"id": "a", "text": "전체 티켓 중 SLA를 지킨 티켓의 비율"},
    {"id": "b", "text": "담당자 출석률"},
    {"id": "c", "text": "서버 가동률"},
    {"id": "d", "text": "이메일 열람률"}
]'::jsonb,
'a',
'예: 100개 티켓 중 95개가 SLA 내 해결되었다면 SLA Compliance는 95%입니다. 주요 성과 지표입니다.',
48),

-- Q49
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'Operational Hours(운영 시간)와 Business Hours의 차이는?',

'[
    {"id": "a", "text": "Operational은 24/7 가능, Business는 근무시간만 해당"},
    {"id": "b", "text": "차이 없음"},
    {"id": "c", "text": "Operational은 해외, Business는 국내"},
    {"id": "d", "text": "Operational은 유료, Business는 무료"}
]'::jsonb,
'a',
'Operational Hours는 실제 IT 지원이 제공되는 시간(24/7 또는 평일만), Business Hours는 SLA 계산에 사용되는 시간입니다.',
49),

-- Q50
('a1b2c3d4-0003-4000-8000-000000000003', 'basic',
'SLA Dashboard에서 확인해야 할 정보가 아닌 것은?',

'[
    {"id": "a", "text": "SLA 위반 티켓 수"},
    {"id": "b", "text": "곧 위반될 위험이 있는 티켓(Due soon)"},
    {"id": "c", "text": "평균 응답/해결 시간"},
    {"id": "d", "text": "담당자의 커피 소비량"}
]'::jsonb,
'd',
'SLA Dashboard는 위반 현황, 위험 티켓, 평균 시간, 준수율 등 서비스 품질 지표를 모니터링합니다.',
50),

-- [심화] SLA 관리 - 10 questions
-- Q51
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'Multi-level SLA Escalation의 설정 예시로 적절한 것은?',

'[
    {"id": "a", "text": "50% 경과 시 팀장 알림, 80% 경과 시 부서장 알림, 100% 시 임원 알림"},
    {"id": "b", "text": "모든 단계에서 동일한 사람에게 알림"},
    {"id": "c", "text": "에스컬레이션 없음"},
    {"id": "d", "text": "무작위 알림"}
]'::jsonb,
'a',
'단계별 Escalation으로 SLA 만료가 가까워질수록 더 높은 직급에 알려 적시 대응을 유도합니다.',
51),

-- Q52
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA의 "Calendar Hours" vs "Business Hours" 모드 선택 기준은?',

'[
    {"id": "a", "text": "24/7 지원이면 Calendar, 평일만 지원이면 Business"},
    {"id": "b", "text": "항상 Calendar 사용"},
    {"id": "c", "text": "항상 Business 사용"},
    {"id": "d", "text": "무작위 선택"}
]'::jsonb,
'a',
'글로벌 24시간 운영 팀은 Calendar Hours, 평일 9-18시 운영 팀은 Business Hours를 사용하여 실제 근무 시간을 반영합니다.',
52),

-- Q53
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA의 "Respond by" 시간이 지났으나 담당자가 Private Note만 남긴 경우?',

'[
    {"id": "a", "text": "SLA 위반으로 간주됨 (Public Reply가 필요)"},
    {"id": "b", "text": "SLA 충족"},
    {"id": "c", "text": "SLA가 연장됨"},
    {"id": "d", "text": "SLA가 리셋됨"}
]'::jsonb,
'a',
'First Response는 일반적으로 고객에게 보이는 Public Reply여야 하며, 내부 메모(Private Note)는 응답으로 인정되지 않습니다.',
53),

-- Q54
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA Policy에 "Holidays" 설정을 추가하는 이유는?',

'[
    {"id": "a", "text": "공휴일을 업무시간에서 제외하여 SLA 타이머가 돌지 않게 함"},
    {"id": "b", "text": "직원 휴가 관리"},
    {"id": "c", "text": "급여 계산"},
    {"id": "d", "text": "이메일 자동 응답"}
]'::jsonb,
'a',
'국가별 공휴일을 설정하면 해당 날짜는 SLA 계산에서 제외되어, 실제 근무일 기준으로 SLA가 적용됩니다.',
54),

-- Q55
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'VIP Customer에게 더 짧은 SLA를 적용하는 방법은?',

'[
    {"id": "a", "text": "별도의 SLA Policy를 생성하고 VIP 그룹에 적용"},
    {"id": "b", "text": "수동으로 매번 우선순위 변경"},
    {"id": "c", "text": "불가능함"},
    {"id": "d", "text": "모든 고객에게 동일 SLA만 적용 가능"}
]'::jsonb,
'a',
'고객 그룹, 계약 등급별로 여러 SLA Policy를 만들고, 조건에 따라 다른 SLA를 자동 적용할 수 있습니다.',
55),

-- Q56
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA "Resolve by" 시간이 지났지만 고객이 해결을 확인하지 않은 경우?',

'[
    {"id": "a", "text": "티켓을 Resolved 상태로 변경한 시간 기준으로 SLA 판단"},
    {"id": "b", "text": "고객 확인 전까지 SLA 위반"},
    {"id": "c", "text": "SLA가 무효화됨"},
    {"id": "d", "text": "SLA가 자동 연장됨"}
]'::jsonb,
'a',
'Resolution Time은 담당자가 티켓을 Resolved로 변경한 시점을 기준으로 측정되며, 고객의 최종 확인과는 무관합니다.',
56),

-- Q57
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA Breach Notification(위반 알림)을 받아야 할 대상은?',

'[
    {"id": "a", "text": "담당 에이전트, 팀 리더, 품질 관리자"},
    {"id": "b", "text": "모든 직원"},
    {"id": "c", "text": "외부 고객만"},
    {"id": "d", "text": "알림 불필요"}
]'::jsonb,
'a',
'SLA 위반은 서비스 품질 문제이므로, 해당 티켓 담당자와 관리자, QA팀에 즉시 알려 재발 방지 조치를 취해야 합니다.',
57),

-- Q58
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA의 "Pause on" 조건으로 적절한 것은?',

'[
    {"id": "a", "text": "Ticket Status = Pending (고객 응답 대기)"},
    {"id": "b", "text": "Ticket Priority = High"},
    {"id": "c", "text": "Agent is online"},
    {"id": "d", "text": "Ticket has attachments"}
]'::jsonb,
'a',
'고객이나 제3자의 응답을 기다리는 Pending 상태에서는 IT팀이 통제할 수 없으므로 SLA를 일시 정지합니다.',
58),

-- Q59
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA Report에서 "Mean Time To Respond(MTTR)"의 의미는?',

'[
    {"id": "a", "text": "티켓 접수부터 최초 응답까지의 평균 시간"},
    {"id": "b", "text": "티켓 총 처리 시간"},
    {"id": "c", "text": "담당자 평균 근무 시간"},
    {"id": "d", "text": "서버 응답 시간"}
]'::jsonb,
'a',
'MTTR(Mean Time To Respond)은 티켓이 생성된 후 담당자가 최초로 응답하기까지 걸린 평균 시간으로, 서비스 신속성 지표입니다.',
59),

-- Q60
('a1b2c3d4-0003-4000-8000-000000000003', 'advanced',
'SLA 개선을 위한 가장 효과적인 전략은?',

'[
    {"id": "a", "text": "자동화 규칙으로 반복 작업 줄이기 + Knowledge Base 강화로 셀프서비스 유도"},
    {"id": "b", "text": "모든 티켓 우선순위를 Low로 설정"},
    {"id": "c", "text": "SLA 목표 시간을 매우 길게 설정"},
    {"id": "d", "text": "티켓 접수 제한"}
]'::jsonb,
'a',
'자동화로 처리 시간을 단축하고, KB로 사용자가 스스로 해결하게 하면 티켓 수가 줄어 SLA 준수율이 향상됩니다.',
60);

-- ============================================
-- 완료 메시지
-- ============================================
DO $$
DECLARE
    total_questions INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_questions FROM quiz_questions 
    WHERE module_id IN (
        SELECT id FROM curriculum_modules WHERE product = 'freshservice'
    );
    
    RAISE NOTICE '====================================';
    RAISE NOTICE 'Quiz Questions Seeding Complete!';
    RAISE NOTICE 'Total questions created: %', total_questions;
    RAISE NOTICE '====================================';
END $$;

-- 검증 쿼리
SELECT 
    cm.name_ko AS module_name,
    qq.difficulty,
    COUNT(*) AS question_count
FROM quiz_questions qq
JOIN curriculum_modules cm ON qq.module_id = cm.id
WHERE cm.product = 'freshservice'
GROUP BY cm.name_ko, cm.display_order, qq.difficulty
ORDER BY cm.display_order, qq.difficulty;
