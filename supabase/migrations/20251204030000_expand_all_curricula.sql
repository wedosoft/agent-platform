-- ============================================
-- 전체 제품 커리큘럼 확장
-- Date: 2025-12-04
-- Freshdesk, Freshchat, Freshdesk Omni, Freshsales
-- ============================================

-- ============================================
-- 1. FRESHDESK 커리큘럼 (5개 모듈)
-- ============================================

INSERT INTO curriculum_modules (target_product_id, target_product_type, name_ko, name_en, slug, description, icon, display_order, estimated_minutes, feature_tags, content_strategy) VALUES
('freshdesk', 'module', '티켓 관리 기초', 'Ticket Management Basics', 'ticket-basics',
 '고객 문의를 티켓으로 관리하는 기본 개념과 워크플로우를 학습합니다.',
 'fa-ticket-alt', 1, 30, ARRAY['ticketing', 'priority', 'status'], 'hybrid'),

('freshdesk', 'module', '옴니채널 지원', 'Omnichannel Support', 'omnichannel',
 '이메일, 전화, 소셜 미디어, 웹폼 등 다양한 채널의 고객 문의를 통합 관리합니다.',
 'fa-globe', 2, 25, ARRAY['email', 'phone', 'social', 'web'], 'hybrid'),

('freshdesk', 'module', '지식 베이스 관리', 'Knowledge Base Management', 'knowledge-base',
 '고객 셀프서비스를 위한 FAQ, 가이드, 솔루션 문서를 작성하고 관리합니다.',
 'fa-book', 3, 30, ARRAY['kb', 'faq', 'self_service', 'article'], 'hybrid'),

('freshdesk', 'module', '자동화 및 워크플로우', 'Automation & Workflow', 'automation',
 '티켓 자동 분류, 배정, 에스컬레이션 등 반복 작업을 자동화합니다.',
 'fa-cogs', 4, 35, ARRAY['automation', 'dispatch', 'scenario', 'sla'], 'hybrid'),

('freshdesk', 'module', '리포팅 및 분석', 'Reporting & Analytics', 'reporting',
 '티켓 볼륨, 에이전트 성과, 고객 만족도 등 핵심 지표를 분석합니다.',
 'fa-chart-bar', 5, 25, ARRAY['reporting', 'analytics', 'csat', 'dashboard'], 'hybrid')

ON CONFLICT (target_product_id, slug) DO UPDATE SET
    name_ko = EXCLUDED.name_ko,
    description = EXCLUDED.description,
    estimated_minutes = EXCLUDED.estimated_minutes,
    feature_tags = EXCLUDED.feature_tags;


-- ============================================
-- 2. FRESHCHAT 커리큘럼 (5개 모듈)
-- ============================================

INSERT INTO curriculum_modules (target_product_id, target_product_type, name_ko, name_en, slug, description, icon, display_order, estimated_minutes, feature_tags, content_strategy) VALUES
('freshchat', 'module', '실시간 채팅 설정', 'Live Chat Setup', 'live-chat-setup',
 'Freshchat 위젯을 웹사이트에 설치하고 기본 설정을 구성합니다.',
 'fa-comments', 1, 20, ARRAY['widget', 'setup', 'installation'], 'hybrid'),

('freshchat', 'module', '챗봇 구성', 'Chatbot Configuration', 'chatbot',
 'Freddy AI 챗봇을 설정하고 자동 응답 플로우를 설계합니다.',
 'fa-robot', 2, 35, ARRAY['chatbot', 'freddy', 'bot_flow', 'automation'], 'hybrid'),

('freshchat', 'module', '메시징 채널 통합', 'Messaging Channels', 'messaging-channels',
 'WhatsApp, Facebook Messenger, LINE 등 메시징 앱을 연동합니다.',
 'fa-mobile-alt', 3, 25, ARRAY['whatsapp', 'messenger', 'line', 'integration'], 'hybrid'),

('freshchat', 'module', '팀 관리 및 라우팅', 'Team Management & Routing', 'team-routing',
 '에이전트 그룹을 구성하고 대화 배정 규칙을 설정합니다.',
 'fa-users', 4, 25, ARRAY['team', 'routing', 'assignment', 'groups'], 'hybrid'),

('freshchat', 'module', '캠페인 및 인앱 메시지', 'Campaigns & In-App Messages', 'campaigns',
 '프로액티브 메시지와 타겟 캠페인으로 고객 참여를 높입니다.',
 'fa-bullhorn', 5, 30, ARRAY['campaign', 'proactive', 'engagement', 'targeting'], 'hybrid')

ON CONFLICT (target_product_id, slug) DO UPDATE SET
    name_ko = EXCLUDED.name_ko,
    description = EXCLUDED.description,
    estimated_minutes = EXCLUDED.estimated_minutes,
    feature_tags = EXCLUDED.feature_tags;


-- ============================================
-- 3. FRESHDESK OMNI 커리큘럼 (4개 번들 전용 모듈)
-- ============================================

INSERT INTO curriculum_modules (target_product_id, target_product_type, name_ko, name_en, slug, description, icon, display_order, estimated_minutes, feature_tags, content_strategy) VALUES
('freshdesk_omni', 'bundle', '통합 워크스페이스 이해', 'Unified Workspace Overview', 'omni-workspace',
 'Freshdesk + Freshchat이 결합된 통합 에이전트 워크스페이스의 개념과 장점을 이해합니다.',
 'fa-layer-group', 1, 25, ARRAY['unified', 'workspace', 'integration'], 'hybrid'),

('freshdesk_omni', 'bundle', '채팅-티켓 전환 플로우', 'Chat to Ticket Flow', 'chat-to-ticket',
 '채팅 대화를 티켓으로 전환하고 컨텍스트를 보존하는 방법을 학습합니다.',
 'fa-exchange-alt', 2, 20, ARRAY['conversion', 'context', 'escalation'], 'hybrid'),

('freshdesk_omni', 'bundle', '옴니채널 라우팅', 'Omnichannel Routing', 'omni-routing',
 '채팅, 이메일, 전화 등 모든 채널의 문의를 통합 라우팅 규칙으로 관리합니다.',
 'fa-random', 3, 30, ARRAY['routing', 'queue', 'skills', 'load_balancing'], 'hybrid'),

('freshdesk_omni', 'bundle', '통합 고객 뷰 활용', 'Unified Customer View', 'customer-360',
 '모든 채널의 고객 이력을 한눈에 파악하고 개인화된 서비스를 제공합니다.',
 'fa-user-circle', 4, 25, ARRAY['customer_360', 'history', 'context', 'personalization'], 'hybrid')

ON CONFLICT (target_product_id, slug) DO UPDATE SET
    name_ko = EXCLUDED.name_ko,
    description = EXCLUDED.description,
    estimated_minutes = EXCLUDED.estimated_minutes,
    feature_tags = EXCLUDED.feature_tags;


-- ============================================
-- 4. FRESHSALES 커리큘럼 (5개 모듈)
-- ============================================

INSERT INTO curriculum_modules (target_product_id, target_product_type, name_ko, name_en, slug, description, icon, display_order, estimated_minutes, feature_tags, content_strategy) VALUES
('freshsales', 'module', 'CRM 기초', 'CRM Basics', 'crm-basics',
 'CRM의 기본 개념과 리드, 연락처, 계정 관리 방법을 학습합니다.',
 'fa-address-book', 1, 30, ARRAY['crm', 'lead', 'contact', 'account'], 'hybrid'),

('freshsales', 'module', '영업 파이프라인', 'Sales Pipeline', 'sales-pipeline',
 '딜 스테이지를 설정하고 영업 기회를 효과적으로 관리합니다.',
 'fa-funnel-dollar', 2, 35, ARRAY['pipeline', 'deal', 'stage', 'forecast'], 'hybrid'),

('freshsales', 'module', '이메일 및 활동 추적', 'Email & Activity Tracking', 'email-tracking',
 '이메일 발송, 열람 추적, 통화 기록 등 영업 활동을 관리합니다.',
 'fa-envelope-open-text', 3, 25, ARRAY['email', 'tracking', 'calls', 'activities'], 'hybrid'),

('freshsales', 'module', '리드 스코어링', 'Lead Scoring', 'lead-scoring',
 'Freddy AI 기반 리드 스코어링으로 우선순위 높은 기회를 식별합니다.',
 'fa-star-half-alt', 4, 30, ARRAY['scoring', 'freddy', 'ai', 'prioritization'], 'hybrid'),

('freshsales', 'module', '영업 자동화', 'Sales Automation', 'sales-automation',
 '시퀀스, 워크플로우를 활용한 영업 프로세스 자동화를 학습합니다.',
 'fa-magic', 5, 30, ARRAY['automation', 'sequence', 'workflow', 'nurturing'], 'hybrid')

ON CONFLICT (target_product_id, slug) DO UPDATE SET
    name_ko = EXCLUDED.name_ko,
    description = EXCLUDED.description,
    estimated_minutes = EXCLUDED.estimated_minutes,
    feature_tags = EXCLUDED.feature_tags;


-- ============================================
-- 확인 쿼리
-- ============================================
SELECT 
    target_product_id,
    target_product_type,
    COUNT(*) as module_count
FROM curriculum_modules
WHERE is_active = true
GROUP BY target_product_id, target_product_type
ORDER BY target_product_id;
