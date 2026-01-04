-- ============================================
-- 시나리오 초기 데이터 삽입 (constants.ts에서 마이그레이션)
-- Date: 2026-01-04
-- Description: 기존 하드코딩된 시나리오 데이터를 DB에 삽입
-- ============================================

-- 1. 카테고리 데이터 삽입
INSERT INTO onboarding.scenario_categories (id, name, name_ko, icon, description, description_ko, display_order) VALUES
('productivity', 'Work Management & Productivity', '업무 관리 및 생산성', 'fa-solid fa-gears', 
 'Learn how to prioritize tasks, manage time efficiently, and improve productivity through clear instructions.',
 '업무 우선순위를 정하고, 시간을 효율적으로 관리하며, 명확한 지시를 통해 생산성을 높이는 방법을 배웁니다.', 1),
('communication', 'Communication & Collaboration', '커뮤니케이션 및 협업', 'fa-solid fa-users',
 'Develop skills to communicate effectively with colleagues and other departments, give and receive constructive feedback, and resolve conflicts.',
 '동료 및 다른 부서와 효과적으로 소통하고, 건설적인 피드백을 주고받으며 갈등을 해결하는 능력을 기릅니다.', 2),
('problem_solving', 'Problem Solving & Self-Management', '문제 해결 및 자기 관리', 'fa-solid fa-lightbulb',
 'Grow as a resilient professional who can handle unexpected problems, learn from mistakes, and prevent burnout.',
 '예상치 못한 문제에 대처하고, 실수를 통해 배우며, 번아웃을 예방하는 등 회복탄력성을 갖춘 전문가로 성장합니다.', 3)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    name_ko = EXCLUDED.name_ko,
    icon = EXCLUDED.icon,
    description = EXCLUDED.description,
    description_ko = EXCLUDED.description_ko,
    display_order = EXCLUDED.display_order,
    updated_at = NOW();

-- 2. 시나리오 데이터 삽입
INSERT INTO onboarding.scenarios (id, category_id, title, title_ko, icon, description, description_ko, display_order) VALUES
('s1', 'productivity', 'Prioritizing Tasks', '업무 우선순위 정하기', 'fa-solid fa-list-check',
 'It''s Monday morning. You need to submit a weekly report by midnight today (important but not urgent), and your manager has assigned you a critical bug fix that needs to be deployed ASAP (important and urgent). You also received an optional team-building survey email. How do you proceed?',
 '월요일 아침입니다. 당신은 오늘 자정까지 주간 보고서를 제출해야 하고(중요하지만, 긴급하지 않음), 매니저로부터는 ASAP(가능한 한 빨리) 배포해야 할 치명적인 버그 수정 작업을 할당받았습니다(중요하고, 긴급함). 또한, 선택 사항인 팀 빌딩 설문조사 이메일도 받았습니다. 어떻게 진행하시겠습니까?', 1),

('s2', 'communication', 'Handling Conflicting Requests', '상충하는 요청 처리하기', 'fa-solid fa-people-arrows',
 'The sales team lead has requested a data analysis report needed for a customer meeting in 2 hours. At the same time, your direct manager has assigned you a task that is part of a major project release. Both seem urgent. What do you do?',
 '영업팀장님이 2시간 후에 있을 고객 미팅에 필요한 데이터 분석 보고서를 요청했습니다. 동시에, 당신의 직속 매니저는 주요 프로젝트 릴리즈의 일부인 업무를 할당했습니다. 두 가지 모두 긴급해 보입니다. 어떻게 하시겠습니까?', 2),

('s3', 'problem_solving', 'Responding to Mistakes', '실수에 대응하기', 'fa-solid fa-person-circle-exclamation',
 'You realized there was a mistake in a data report that was already sent to several department heads. This could lead to wrong decisions being made. What is your immediate next action?',
 '여러 부서장에게 이미 발송된 데이터 보고서에 실수가 있었다는 것을 깨달았습니다. 이로 인해 잘못된 의사결정이 내려질 수 있습니다. 당신의 즉각적인 다음 조치는 무엇입니까?', 3),

('s4', 'productivity', 'Managing Time', '시간 관리하기', 'fa-solid fa-clock',
 'You have a large, complex project that requires a lot of focus, but your day is filled with constant notifications, emails, and meeting invitations. How do you make progress on the important project?',
 '집중이 많이 필요한 크고 복잡한 프로젝트가 있지만, 하루 종일 끊임없는 알림, 이메일, 회의 초대로 가득 차 있습니다. 중요한 프로젝트에서 진전을 이루기 위해 어떻게 하시겠습니까?', 4),

('s5', 'communication', 'Giving Constructive Feedback to a Colleague', '동료에게 건설적인 피드백 주기', 'fa-solid fa-comments',
 'You noticed that your colleague misinterpreted some important data in their presentation materials. They are scheduled to present to the entire team tomorrow morning. How do you deliver the feedback?',
 '당신의 동료가 발표 자료에서 몇 가지 중요한 데이터를 잘못 해석한 것을 발견했습니다. 내일 아침 전체 팀 앞에서 발표할 예정입니다. 어떻게 피드백을 전달하시겠습니까?', 5),

('s6', 'productivity', 'Handling Vague and Unclear Tasks', '모호하고 불분명한 업무 처리', 'fa-solid fa-lightbulb-question',
 'Your manager asked you to prepare "some ideas to address customer churn" by next week. There was no explanation about the specific format or expected deliverable. How do you approach this?',
 '매니저가 "고객 이탈 문제를 해결하기 위한 몇 가지 아이디어"를 다음 주까지 준비해달라고 요청했습니다. 구체적인 형식이나 기대 결과물에 대한 설명이 없습니다. 어떻게 접근하시겠습니까?', 6),

('s7', 'problem_solving', 'Unexpected Project Failure', '예상치 못한 프로젝트 실패', 'fa-solid fa-person-digging',
 'A small feature you were responsible for showed serious defects in the final testing phase and cannot be released. There are team members who had expectations for this feature. How do you share the situation?',
 '당신이 담당했던 작은 기능 개발이 최종 테스트 단계에서 심각한 결함을 보이며 출시가 불가능하게 되었습니다. 이 기능에 기대를 걸었던 팀원들이 있습니다. 어떻게 상황을 공유하시겠습니까?', 7),

('s8', 'problem_solving', 'Detecting Early Signs of Burnout', '번아웃의 초기 징후 감지', 'fa-solid fa-battery-quarter',
 'You have been working overtime frequently in recent weeks, and your interest and concentration in work have noticeably decreased. It''s hard to get up in the morning and you get irritated by small things. How do you cope?',
 '최근 몇 주간 야근이 잦았고, 업무에 대한 흥미와 집중력이 눈에 띄게 떨어졌습니다. 아침에 일어나는 것이 힘들고 사소한 일에도 짜증이 납니다. 어떻게 대처하시겠습니까?', 8),

('s9', 'communication', 'Collaboration Conflict with Other Departments', '타 부서와의 협업 갈등', 'fa-solid fa-handshake-angle',
 'You need deliverables from the design team for a project, but they are uncooperative, saying they have different internal priorities. The project deadline is approaching. How do you resolve this?',
 '프로젝트를 위해 디자인 팀의 결과물이 필요하지만, 그들은 내부 우선순위가 다르다며 비협조적입니다. 프로젝트 마감일은 다가오고 있습니다. 어떻게 해결하시겠습니까?', 9),

('s10', 'communication', 'Dealing with Hard-to-Accept Feedback', '받아들이기 힘든 피드백에 대처하기', 'fa-solid fa-user-pen',
 'During a code review, a senior colleague left rather direct feedback saying your code is "very inefficient and doesn''t meet industry standards." It''s in a public channel where all team members can see. You feel hurt, but what is the most professional way to respond?',
 '코드 리뷰 중, 시니어 동료가 당신의 코드에 대해 ''매우 비효율적이고 업계 표준에 맞지 않는다''는 다소 직설적인 피드백을 남겼습니다. 공개적인 채널이라 다른 팀원들도 모두 볼 수 있는 상황입니다. 기분이 상했지만, 어떻게 반응하는 것이 가장 프로페셔널할까요?', 10),

('s11', 'problem_solving', 'Reporting Potential Project Delay to Manager', '매니저에게 프로젝트 지연 가능성 보고하기', 'fa-solid fa-person-chalkboard',
 'The deadline for your task is approaching, but due to unexpected technical issues, it seems difficult to complete on time. There are still a few days left, but at this rate, you are likely to miss the deadline. What do you do?',
 '당신이 맡은 업무의 마감일이 다가오고 있지만, 예상치 못한 기술적 문제로 인해 제시간에 완료하기 어려울 것 같습니다. 아직 며칠의 시간이 남았지만, 이대로라면 마감일을 놓칠 가능성이 높습니다. 어떻게 하시겠습니까?', 11),

('s12', 'productivity', 'Clarifying Incomplete Task Instructions', '불완전한 업무 지시 명확히 하기', 'fa-solid fa-circle-question',
 'Before going on vacation, a colleague left a simple note: "Please extract a list of inactive users from this database and send it to the marketing team." However, there was no mention of the criteria for "inactive users" (e.g., last login 30, 60, or 90 days?) or the data format to deliver. What do you do?',
 '동료가 휴가를 떠나기 전, ''이 데이터베이스에서 비활성 사용자 목록을 추출해서 마케팅팀에 전달해주세요''라는 간단한 메모를 남겼습니다. 하지만 ''비활성 사용자''의 기준(예: 마지막 로그인 30일, 60일, 90일?)이나 전달해야 할 데이터 형식에 대한 언급이 없습니다. 어떻게 하시겠습니까?', 12)
ON CONFLICT (id) DO UPDATE SET
    category_id = EXCLUDED.category_id,
    title = EXCLUDED.title,
    title_ko = EXCLUDED.title_ko,
    icon = EXCLUDED.icon,
    description = EXCLUDED.description,
    description_ko = EXCLUDED.description_ko,
    display_order = EXCLUDED.display_order,
    updated_at = NOW();

-- 3. 선택지 데이터 삽입
-- s1: 업무 우선순위 정하기
INSERT INTO onboarding.scenario_choices (id, scenario_id, text, text_ko, display_order, is_recommended) VALUES
('c1-1', 's1', 'Start working on the critical bug fix immediately.', '즉시 치명적인 버그 수정 작업부터 시작한다.', 1, TRUE),
('c1-2', 's1', 'Work on the weekly report first since it has a clear deadline.', '명확한 마감일이 있는 주간 보고서부터 먼저 작업한다.', 2, FALSE),
('c1-3', 's1', 'Handle the simple team-building survey first to get it out of the way.', '간단한 팀 빌딩 설문조사를 먼저 처리해서 끝내버린다.', 3, FALSE),
('c1-4', 's1', 'Ask the manager which task should be prioritized.', '매니저에게 어떤 업무를 우선적으로 처리해야 할지 물어본다.', 4, FALSE),

-- s2: 상충하는 요청 처리하기
('c2-1', 's2', 'Stop current work and immediately start writing the sales report.', '현재 하던 업무를 중단하고 즉시 영업 보고서 작성을 시작한다.', 1, FALSE),
('c2-2', 's2', 'Tell the sales team lead that you are too busy to help right now.', '영업팀장님에게 지금 바빠서 도와줄 수 없다고 말한다.', 2, FALSE),
('c2-3', 's2', 'Inform your direct manager about the new request and ask for priority adjustment.', '직속 매니저에게 새로운 요청에 대해 알리고 우선순위 조정을 요청한다.', 3, TRUE),
('c2-4', 's2', 'Try to handle both tasks simultaneously through multitasking.', '멀티태스킹으로 두 가지 업무를 동시에 처리하려고 노력한다.', 4, FALSE),

-- s3: 실수에 대응하기
('c3-1', 's3', 'Wait until someone notices the mistake.', '누군가 실수를 알아챌 때까지 일단 기다려본다.', 1, FALSE),
('c3-2', 's3', 'Immediately send a follow-up email to all recipients acknowledging the mistake and providing a timeline for the corrected report.', '즉시 모든 수신자에게 실수를 인정하고 수정된 보고서의 타임라인을 안내하는 후속 이메일을 보낸다.', 2, TRUE),
('c3-3', 's3', 'Quietly fix the report and resend it, hoping no one noticed the original.', '아무도 원본을 눈치채지 못했기를 바라며 조용히 보고서를 수정하여 다시 보낸다.', 3, FALSE),
('c3-4', 's3', 'Before telling anyone, spend a few hours trying to figure out exactly why the mistake happened.', '누구에게 알리기 전에, 먼저 몇 시간 동안 실수가 왜 발생했는지 정확히 파악하려고 노력한다.', 4, FALSE),

-- s4: 시간 관리하기
('c4-1', 's4', 'Set "focus time" on your calendar for a few hours and turn off all notifications during that time.', '캘린더에 "집중 시간"을 몇 시간 설정하고 그동안 모든 알림을 끈다.', 1, TRUE),
('c4-2', 's4', 'Respond immediately to every email and notification as they come in to stay on top of everything.', '모든 상황을 파악하기 위해 이메일과 알림이 올 때마다 즉시 응답한다.', 2, FALSE),
('c4-3', 's4', 'Work on the project late at night when there are fewer distractions.', '방해 요소가 적은 밤늦게 프로젝트 작업을 한다.', 3, FALSE),
('c4-4', 's4', 'Complain to the manager that there are too many meetings.', '매니저에게 회의가 너무 많다고 불평한다.', 4, FALSE),

-- s5: 동료에게 건설적인 피드백 주기
('c5-1', 's5', 'Talk to them privately and quietly so they don''t get embarrassed in front of others.', '다른 사람들 앞에서 망신당하지 않도록 개인적으로 조용히 이야기한다.', 1, TRUE),
('c5-2', 's5', 'Post the corrections in the team-wide chat channel for the sake of team accuracy.', '팀의 정확성을 위해 팀 전체 채팅 채널에 수정 사항을 게시한다.', 2, FALSE),
('c5-3', 's5', 'Say nothing to avoid conflict. They will probably notice it themselves.', '갈등을 피하기 위해 아무 말도 하지 않는다. 아마 스스로 알아챌 것이다.', 3, FALSE),
('c5-4', 's5', 'Report the issue to the manager without talking to the colleague directly.', '매니저에게 직접 말하지 않고 이 문제를 알린다.', 4, FALSE),

-- s6: 모호하고 불분명한 업무 처리
('c6-1', 's6', 'Send a follow-up email with clarifying questions (goals, scope, target audience, etc.).', '요구사항을 명확히 하기 위해 후속 질문(목표, 범위, 대상 등)이 담긴 이메일을 보낸다.', 1, TRUE),
('c6-2', 's6', 'Start working in the direction I think is best and check in midway.', '일단 내가 생각하는 최선의 방향으로 작업을 시작하고 중간에 확인받는다.', 2, FALSE),
('c6-3', 's6', 'Ignore the request for now since the manager seems too busy, and handle other urgent tasks.', '매니저가 너무 바빠 보이니, 일단 요청을 무시하고 다른 긴급한 업무를 처리한다.', 3, FALSE),
('c6-4', 's6', 'Start extensive research and write a long report with as many ideas as possible.', '광범위한 조사를 시작하고 가능한 한 많은 아이디어를 담은 긴 보고서를 작성한다.', 4, FALSE),

-- s7: 예상치 못한 프로젝트 실패
('c7-1', 's7', 'Share the problem immediately in a team meeting, transparently explaining the cause I identified and future plans.', '팀 회의에서 문제를 즉시 공유하고, 내가 파악한 원인과 향후 계획을 투명하게 밝힌다.', 1, TRUE),
('c7-2', 's7', 'Find external factors to blame to minimize my responsibility.', '다른 사람을 탓할 만한 외부 요인을 찾아내어 내 책임을 최소화한다.', 2, FALSE),
('c7-3', 's7', 'Delay the official announcement as much as possible, hoping the problem will be quietly forgotten.', '문제가 조용히 잊히기를 바라며 공식적인 발표를 최대한 미룬다.', 3, FALSE),
('c7-4', 's7', 'Only inform the manager privately and let them communicate to the team members.', '매니저에게만 개인적으로 알리고, 팀원들에게는 매니저가 전달하도록 한다.', 4, FALSE),

-- s8: 번아웃의 초기 징후 감지
('c8-1', 's8', 'Request a 1:1 meeting with the manager to honestly discuss current workload and mental state, and explore solutions.', '매니저와 1:1 면담을 신청하여 현재 업무량과 정신적 상태에 대해 솔직하게 논의하고 해결책을 모색한다.', 1, TRUE),
('c8-2', 's8', 'Just endure it and keep working hard because it might look unprofessional. It will get better soon.', '프로답지 못하게 보일까 봐 그냥 참고 계속 열심히 일한다. 곧 나아질 것이다.', 2, FALSE),
('c8-3', 's8', 'Complain to colleagues but don''t take any practical action to solve it.', '동료들에게 불평을 늘어놓지만, 실질적인 해결을 위한 행동은 하지 않는다.', 3, FALSE),
('c8-4', 's8', 'Take time off without telling anyone and rest for a few days. But don''t address the root cause.', '아무에게도 알리지 않고 휴가를 내서 며칠 쉰다. 하지만 근본적인 원인은 해결하지 않는다.', 4, FALSE),

-- s9: 타 부서와의 협업 갈등
('c9-1', 's9', 'Contact the design team leader to explain how this project contributes to overall company goals and discuss priority adjustment.', '디자인 팀 리더에게 연락하여, 이 프로젝트가 회사 전체 목표에 어떻게 기여하는지 설명하고 우선순위 조정을 논의한다.', 1, TRUE),
('c9-2', 's9', 'Immediately report the problem to my manager and delegate all resolution to them.', '내 매니저에게 즉시 문제를 보고하고 모든 해결을 위임한다.', 2, FALSE),
('c9-3', 's9', 'Start creating design mockups myself without the design team''s help.', '디자인 팀의 도움 없이 내가 직접 디자인 시안을 만들기 시작한다.', 3, FALSE),
('c9-4', 's9', 'Mention in a public channel that the project is delayed because the design team is not cooperating.', '공개적인 채널에서 디자인 팀이 협조하지 않아 프로젝트가 지연되고 있다고 언급한다.', 4, FALSE),

-- s10: 받아들이기 힘든 피드백에 대처하기
('c10-1', 's10', 'React emotionally to the feedback and post a comment defending the merits of my code.', '피드백에 감정적으로 반응하며 내 코드의 장점을 방어하는 댓글을 단다.', 1, FALSE),
('c10-2', 's10', 'Ignore the feedback and quietly fix the code. I want to avoid arguments.', '피드백을 무시하고 조용히 코드를 수정한다. 논쟁을 피하고 싶다.', 2, FALSE),
('c10-3', 's10', 'Publicly respond "Thank you for the feedback. Could you show me specific examples of what to improve?" to turn it into a learning opportunity.', '공개적으로 ''피드백 감사합니다. 어떤 부분을 구체적으로 개선하면 좋을지 예시를 보여주실 수 있나요?''라고 질문하여 학습의 기회로 삼는다.', 3, TRUE),
('c10-4', 's10', 'Send a private message to the senior colleague expressing displeasure.', '시니어 동료에게 개인 메시지를 보내 불쾌감을 표현한다.', 4, FALSE),

-- s11: 매니저에게 프로젝트 지연 가능성 보고하기
('c11-1', 's11', 'Work overtime alone until the day before the deadline trying to somehow solve it. I want to deliver bad news as late as possible.', '마감일 전날까지 어떻게든 해결해보려고 혼자 야근하며 노력한다. 나쁜 소식은 최대한 늦게 알리고 싶다.', 1, FALSE),
('c11-2', 's11', 'Immediately share the situation with the manager. Communicate the progress so far, the problem that occurred, and the methods I''ve tried to solve it.', '즉시 매니저에게 상황을 공유한다. 현재까지의 진행 상황, 발생한 문제, 그리고 해결을 위해 시도한 방법들을 함께 전달한다.', 2, TRUE),
('c11-3', 's11', 'Quietly ask another colleague for help without telling the manager.', '다른 동료에게 조용히 도움을 요청하고, 매니저에게는 알리지 않는다.', 3, FALSE),
('c11-4', 's11', 'Continue working without any special action, hoping I can meet the deadline.', '마감일을 맞출 수 있을 것이라고 희망하며 별다른 조치 없이 계속 일한다.', 4, FALSE),

-- s12: 불완전한 업무 지시 명확히 하기
('c12-1', 's12', 'Extract data based on my arbitrary decision of "last login 60 days" and deliver it as a basic CSV file.', '내 임의대로 ''마지막 로그인 60일''을 기준으로 데이터를 추출하고, 기본 CSV 파일로 전달한다.', 1, FALSE),
('c12-2', 's12', 'Contact the marketing team directly to ask what criteria and format of data they need.', '마케팅팀에 직접 연락하여 어떤 기준과 형식의 데이터가 필요한지 물어본다.', 2, TRUE),
('c12-3', 's12', 'Try to urgently contact the colleague on vacation to get clear instructions.', '휴가 중인 동료에게 긴급하게 연락하여 명확한 지시를 받으려고 시도한다.', 3, FALSE),
('c12-4', 's12', 'Put the task on hold until the colleague returns from vacation since the instructions are not clear.', '지시가 명확하지 않으므로, 동료가 휴가에서 돌아올 때까지 해당 업무를 보류한다.', 4, FALSE)
ON CONFLICT (id) DO UPDATE SET
    scenario_id = EXCLUDED.scenario_id,
    text = EXCLUDED.text,
    text_ko = EXCLUDED.text_ko,
    display_order = EXCLUDED.display_order,
    is_recommended = EXCLUDED.is_recommended,
    updated_at = NOW();
