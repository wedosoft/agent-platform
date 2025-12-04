-- ============================================
-- Freshworks 제품 그래프 스키마
-- Date: 2025-12-04
-- Description: 모듈/번들/애드온 관계를 명확히 구분하는 스키마
-- 
-- 지원 제품:
--   - Freshdesk (독립 모듈)
--   - Freshchat (독립 모듈, Omni 하위)
--   - Freshdesk Omni (번들: Freshdesk + Freshchat)
--   - Freshsales (독립 모듈, Omni 애드온 가능)
--   - Freshservice (독립 모듈, ITSM)
-- ============================================

-- ============================================
-- 1. Product Modules (독립 제품 모듈)
-- ============================================
CREATE TABLE IF NOT EXISTS product_modules (
    id VARCHAR(50) PRIMARY KEY,  -- 'freshdesk', 'freshchat', 'freshsales', 'freshservice'
    
    -- 기본 정보
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100) NOT NULL,
    
    -- 도메인 분류
    domain VARCHAR(50) NOT NULL,  -- 'customer_service', 'sales_marketing', 'itsm'
    
    -- Freddy AI 지원 여부
    freddy_ai_enabled BOOLEAN DEFAULT false,
    
    -- 기능 모듈 상세 (JSON)
    capabilities JSONB NOT NULL DEFAULT '[]',
    -- 예: [{"id": "ticketing", "name": "티켓 관리", "core": true}]
    
    -- RAG 검색용 키워드
    rag_product_keys TEXT[] NOT NULL DEFAULT '{}',
    -- 예: ['freshdesk', 'fd'] - 문서 필터링에 사용
    
    -- 로고/아이콘
    logo_url TEXT,
    icon VARCHAR(50),
    color_primary VARCHAR(20),
    
    -- 설명
    description TEXT,
    description_ko TEXT,
    
    -- 메타데이터
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_product_modules_domain ON product_modules(domain);
CREATE INDEX IF NOT EXISTS idx_product_modules_active ON product_modules(is_active) WHERE is_active = true;

COMMENT ON TABLE product_modules IS '독립 제품 모듈 (Freshdesk, Freshchat, Freshsales, Freshservice 등)';

-- ============================================
-- 2. Product Bundles (통합 번들)
-- ============================================
CREATE TABLE IF NOT EXISTS product_bundles (
    id VARCHAR(50) PRIMARY KEY,  -- 'freshdesk_omni', 'freshsales_suite'
    
    -- 기본 정보
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100) NOT NULL,
    
    -- 번들 구성
    base_module_ids TEXT[] NOT NULL,  -- ['freshdesk', 'freshchat']
    
    -- 통합 유형
    integration_type VARCHAR(30) NOT NULL,
    -- 'native_unified': 네이티브 통합 (Freshdesk Omni)
    -- 'connected_suite': 연결형 통합 (Freshsales Suite)
    
    -- 워크스페이스 유형
    workspace_type VARCHAR(20) NOT NULL,
    -- 'unified': 단일 워크스페이스
    -- 'integrated': 통합 뷰
    -- 'connected': 연결된 별도 앱
    
    -- RAG 검색용 키워드
    rag_product_keys TEXT[] NOT NULL DEFAULT '{}',
    
    -- 번들 특성 (JSON)
    integration_features JSONB,
    -- 예: {"shared_contacts": true, "unified_inbox": true, "context_preservation": "full"}
    
    -- 가격 혜택
    pricing_advantage_percent DECIMAL(5,2) DEFAULT 0,  -- 번들 할인율
    
    -- 설명
    description TEXT,
    description_ko TEXT,
    
    -- 메타데이터
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_bundles_active ON product_bundles(is_active) WHERE is_active = true;

COMMENT ON TABLE product_bundles IS '통합 번들 제품 (Freshdesk Omni, Freshsales Suite 등)';

-- ============================================
-- 3. Product Relationships (제품 관계 그래프)
-- ============================================
CREATE TABLE IF NOT EXISTS product_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 관계 정의
    source_id VARCHAR(50) NOT NULL,  -- 출발점 (모듈 또는 번들)
    source_type VARCHAR(20) NOT NULL,  -- 'module' or 'bundle'
    target_id VARCHAR(50) NOT NULL,  -- 도착점 (모듈 또는 번들)
    target_type VARCHAR(20) NOT NULL,  -- 'module' or 'bundle'
    
    -- 관계 유형
    relationship_type VARCHAR(30) NOT NULL,
    -- 'bundles_with': A + B → Bundle (번들 생성)
    -- 'addon_to': A는 B의 애드온으로 사용 가능
    -- 'shares_with': A ↔ B 양방향 데이터 공유
    -- 'integrates_with': API 기반 통합
    -- 'included_in': A는 B에 포함됨 (예: Freshchat → Freshdesk Omni)
    -- 'replaces': A는 B의 상위 버전 (업그레이드 경로)
    
    -- 양방향 여부
    bidirectional BOOLEAN DEFAULT false,
    
    -- 통합 특성 (addon_to, integrates_with용)
    integration_characteristics JSONB,
    -- 예: {"conversation_to_ticket": true, "shared_contact_db": true}
    
    -- 결과 번들 (bundles_with용)
    result_bundle_id VARCHAR(50) REFERENCES product_bundles(id),
    
    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_rel_source ON product_relationships(source_id, source_type);
CREATE INDEX IF NOT EXISTS idx_product_rel_target ON product_relationships(target_id, target_type);
CREATE INDEX IF NOT EXISTS idx_product_rel_type ON product_relationships(relationship_type);

COMMENT ON TABLE product_relationships IS '제품 간 관계 그래프 (번들, 애드온, 통합 등)';

-- ============================================
-- 4. Addon Configurations (애드온 제약 조건)
-- ============================================
CREATE TABLE IF NOT EXISTS addon_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 애드온 정의
    addon_module_id VARCHAR(50) NOT NULL REFERENCES product_modules(id),
    target_bundle_id VARCHAR(50) NOT NULL REFERENCES product_bundles(id),
    
    -- 통합 깊이
    integration_depth VARCHAR(20) NOT NULL,
    -- 'deep': 깊은 통합 (데이터 공유, 워크플로우 통합)
    -- 'shared': 공유 사용 (동일 리소스 활용)
    -- 'lightweight': 가벼운 통합 (API 연동)
    
    -- 제약 조건 (JSON 배열)
    constraints JSONB NOT NULL DEFAULT '[]',
    -- 예: [
    --   {"type": "user_ratio", "min": "admins", "max": "licenses"},
    --   {"type": "plan_matching", "required_plans": ["pro", "enterprise"]},
    --   {"type": "feature_dependency", "requires": ["crm_sync"]}
    -- ]
    
    -- 필수 기능 의존성
    required_features TEXT[] DEFAULT '{}',
    
    -- 권장 설정
    recommended_settings JSONB,
    
    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_addon_config_addon ON addon_configurations(addon_module_id);
CREATE INDEX IF NOT EXISTS idx_addon_config_target ON addon_configurations(target_bundle_id);

COMMENT ON TABLE addon_configurations IS '애드온 설치 시 제약 조건 및 권장 설정';

-- ============================================
-- 5. Curriculum Modules (학습 커리큘럼)
-- ============================================
CREATE TABLE IF NOT EXISTS curriculum_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 제품 연결 (모듈 또는 번들)
    target_product_id VARCHAR(50) NOT NULL,
    target_product_type VARCHAR(20) NOT NULL,
    -- 'module': 독립 제품 모듈 (product_modules.id)
    -- 'bundle': 통합 번들 (product_bundles.id)
    -- 'addon': 애드온 시나리오 (예: Freshsales → Omni 연동)
    
    -- 기본 정보
    name_ko VARCHAR(200) NOT NULL,
    name_en VARCHAR(200),
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    
    -- 학습 정보
    display_order INT DEFAULT 0,
    estimated_minutes INT DEFAULT 30,
    learning_objectives JSONB,  -- ['목표1', '목표2', ...]
    
    -- 콘텐츠 전략
    content_strategy VARCHAR(20) DEFAULT 'hybrid',
    -- 'db_only': DB 정적 콘텐츠만 사용
    -- 'rag_only': RAG 검색만 사용
    -- 'hybrid': DB 우선, RAG 보조
    
    -- KB 카테고리 연결 (옵션)
    kb_category_slug VARCHAR(100),
    
    -- 선행 학습 (권장, 강제 아님)
    prerequisite_module_ids UUID[] DEFAULT '{}',
    
    -- 관련 기능 태그
    feature_tags TEXT[] DEFAULT '{}',
    -- 예: ['ticketing', 'automation', 'sla']
    
    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 유니크 제약
    UNIQUE(target_product_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_curriculum_modules_target ON curriculum_modules(target_product_id, target_product_type);
CREATE INDEX IF NOT EXISTS idx_curriculum_modules_slug ON curriculum_modules(slug);
CREATE INDEX IF NOT EXISTS idx_curriculum_modules_order ON curriculum_modules(target_product_id, display_order);
CREATE INDEX IF NOT EXISTS idx_curriculum_modules_active ON curriculum_modules(is_active) WHERE is_active = true;

COMMENT ON TABLE curriculum_modules IS '학습 커리큘럼 모듈 (제품별 학습 단위)';
COMMENT ON COLUMN curriculum_modules.target_product_type IS 'module=독립제품, bundle=번들, addon=애드온 시나리오';

-- ============================================
-- 6. Module Progress (학습 진도)
-- ============================================
CREATE TABLE IF NOT EXISTS module_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 세션/사용자 연결
    session_id VARCHAR(100) NOT NULL,
    module_id UUID NOT NULL REFERENCES curriculum_modules(id) ON DELETE CASCADE,
    
    -- 학습 상태
    status VARCHAR(20) DEFAULT 'not_started',
    -- 'not_started', 'learning', 'quiz_ready', 'completed'
    
    -- 학습 시간 추적
    learning_started_at TIMESTAMPTZ,
    learning_completed_at TIMESTAMPTZ,
    total_learning_seconds INT DEFAULT 0,
    
    -- 퀴즈 결과
    quiz_score INT,
    quiz_attempts INT DEFAULT 0,
    quiz_passed_at TIMESTAMPTZ,
    
    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 유니크 제약
    UNIQUE(session_id, module_id)
);

CREATE INDEX IF NOT EXISTS idx_module_progress_session ON module_progress(session_id);
CREATE INDEX IF NOT EXISTS idx_module_progress_module ON module_progress(module_id);
CREATE INDEX IF NOT EXISTS idx_module_progress_status ON module_progress(status);

COMMENT ON TABLE module_progress IS '사용자별 모듈 학습 진도';

-- ============================================
-- 7. 기존 module_contents 테이블 연결 업데이트
-- (module_contents는 이미 존재하므로 FK만 추가)
-- ============================================
-- module_contents 테이블의 module_id가 curriculum_modules.id를 참조하도록
-- 단, 기존 데이터가 있으므로 나중에 별도로 데이터 마이그레이션 필요

-- ============================================
-- 초기 데이터: 제품 모듈
-- ============================================
INSERT INTO product_modules (id, name, name_ko, domain, freddy_ai_enabled, capabilities, rag_product_keys, description_ko, display_order) VALUES

-- Customer Service Domain
('freshdesk', 'Freshdesk', 'Freshdesk', 'customer_service', true,
 '[
   {"id": "ticketing", "name": "티켓 관리", "name_ko": "티켓 관리", "core": true},
   {"id": "knowledge_base", "name": "Knowledge Base", "name_ko": "지식 베이스", "core": true},
   {"id": "automation", "name": "Automation", "name_ko": "자동화", "core": false},
   {"id": "reporting", "name": "Reporting", "name_ko": "리포팅", "core": false},
   {"id": "sla", "name": "SLA Management", "name_ko": "SLA 관리", "core": false}
 ]'::jsonb,
 ARRAY['freshdesk', 'fd'],
 '옴니채널 고객 지원 플랫폼. 이메일, 전화, 채팅, 소셜 미디어 등 다양한 채널의 고객 문의를 통합 관리합니다.',
 1),

('freshchat', 'Freshchat', 'Freshchat', 'customer_service', true,
 '[
   {"id": "live_chat", "name": "Live Chat", "name_ko": "실시간 채팅", "core": true},
   {"id": "chatbot", "name": "Chatbot", "name_ko": "챗봇", "core": true},
   {"id": "messaging", "name": "Messaging", "name_ko": "메시징", "core": false}
 ]'::jsonb,
 ARRAY['freshchat', 'fc'],
 '모던 메시징 솔루션. 웹사이트, 모바일 앱, 소셜 메신저에서 고객과 실시간 대화할 수 있습니다.',
 2),

-- Sales & Marketing Domain
('freshsales', 'Freshsales', 'Freshsales', 'sales_marketing', true,
 '[
   {"id": "crm", "name": "CRM", "name_ko": "CRM", "core": true},
   {"id": "pipeline", "name": "Sales Pipeline", "name_ko": "영업 파이프라인", "core": true},
   {"id": "email_tracking", "name": "Email Tracking", "name_ko": "이메일 추적", "core": false},
   {"id": "lead_scoring", "name": "Lead Scoring", "name_ko": "리드 스코어링", "core": false}
 ]'::jsonb,
 ARRAY['freshsales', 'fs'],
 'AI 기반 CRM 플랫폼. 영업 파이프라인 관리, 리드 스코어링, 이메일 추적 등 영업 전 과정을 지원합니다.',
 3),

-- ITSM Domain
('freshservice', 'Freshservice', 'Freshservice', 'itsm', true,
 '[
   {"id": "ticketing", "name": "Ticket Management", "name_ko": "티켓 관리", "core": true},
   {"id": "asset_management", "name": "Asset Management", "name_ko": "자산 관리", "core": true},
   {"id": "cmdb", "name": "CMDB", "name_ko": "CMDB", "core": true},
   {"id": "change_management", "name": "Change Management", "name_ko": "변경 관리", "core": false},
   {"id": "problem_management", "name": "Problem Management", "name_ko": "문제 관리", "core": false},
   {"id": "service_catalog", "name": "Service Catalog", "name_ko": "서비스 카탈로그", "core": false},
   {"id": "workflow_automation", "name": "Workflow Automation", "name_ko": "워크플로우 자동화", "core": false}
 ]'::jsonb,
 ARRAY['freshservice', 'fsvc'],
 'IT 서비스 관리(ITSM) 플랫폼. ITIL 기반의 인시던트, 문제, 변경, 자산 관리를 지원합니다.',
 4)

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    name_ko = EXCLUDED.name_ko,
    domain = EXCLUDED.domain,
    freddy_ai_enabled = EXCLUDED.freddy_ai_enabled,
    capabilities = EXCLUDED.capabilities,
    rag_product_keys = EXCLUDED.rag_product_keys,
    description_ko = EXCLUDED.description_ko,
    display_order = EXCLUDED.display_order,
    updated_at = NOW();

-- ============================================
-- 초기 데이터: 번들
-- ============================================
INSERT INTO product_bundles (id, name, name_ko, base_module_ids, integration_type, workspace_type, rag_product_keys, integration_features, pricing_advantage_percent, description_ko, display_order) VALUES

('freshdesk_omni', 'Freshdesk Omni', 'Freshdesk Omni', 
 ARRAY['freshdesk', 'freshchat'],
 'native_unified',
 'unified',
 ARRAY['freshdesk-omni', 'omni', 'fdo'],
 '{
   "unified_inbox": true,
   "shared_contacts": true,
   "conversation_to_ticket": true,
   "context_preservation": "full",
   "single_workspace": true,
   "cross_channel_history": true
 }'::jsonb,
 20.00,
 'Freshdesk + Freshchat 통합 번들. 단일 워크스페이스에서 티켓과 채팅을 통합 관리합니다. 대화가 티켓으로 자동 전환되며 전체 컨텍스트가 보존됩니다.',
 1)

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    name_ko = EXCLUDED.name_ko,
    base_module_ids = EXCLUDED.base_module_ids,
    integration_type = EXCLUDED.integration_type,
    workspace_type = EXCLUDED.workspace_type,
    rag_product_keys = EXCLUDED.rag_product_keys,
    integration_features = EXCLUDED.integration_features,
    pricing_advantage_percent = EXCLUDED.pricing_advantage_percent,
    description_ko = EXCLUDED.description_ko,
    display_order = EXCLUDED.display_order,
    updated_at = NOW();

-- ============================================
-- 초기 데이터: 제품 관계
-- ============================================
INSERT INTO product_relationships (source_id, source_type, target_id, target_type, relationship_type, result_bundle_id, integration_characteristics) VALUES

-- Freshdesk + Freshchat → Freshdesk Omni
('freshdesk', 'module', 'freshchat', 'module', 'bundles_with', 'freshdesk_omni',
 '{"conversation_to_ticket": true, "shared_contact_db": true, "unified_workspace": true}'::jsonb),

-- Freshchat → Freshdesk Omni (포함 관계)
('freshchat', 'module', 'freshdesk_omni', 'bundle', 'included_in', NULL, NULL),

-- Freshsales → Freshdesk Omni (애드온 가능)
('freshsales', 'module', 'freshdesk_omni', 'bundle', 'addon_to', NULL,
 '{"crm_sync": true, "contact_enrichment": true, "deal_context": true}'::jsonb)

ON CONFLICT DO NOTHING;

-- ============================================
-- 초기 데이터: 애드온 설정
-- ============================================
INSERT INTO addon_configurations (addon_module_id, target_bundle_id, integration_depth, constraints, required_features, recommended_settings) VALUES

('freshsales', 'freshdesk_omni', 'deep',
 '[
   {"type": "user_ratio", "description": "Freshsales 사용자는 Omni 라이선스 수를 초과할 수 없음", "min": "admins", "max": "licenses"},
   {"type": "plan_matching", "description": "Pro 이상 플랜 필요", "required_plans": ["pro", "enterprise"]},
   {"type": "feature_dependency", "description": "CRM 동기화 기능 필수", "requires": ["crm_sync"]}
 ]'::jsonb,
 ARRAY['crm_sync', 'contact_management'],
 '{"auto_contact_sync": true, "deal_visibility": "shared", "activity_logging": true}'::jsonb)

ON CONFLICT DO NOTHING;

-- ============================================
-- 초기 데이터: 커리큘럼 모듈 (Freshservice)
-- ============================================
INSERT INTO curriculum_modules (target_product_id, target_product_type, name_ko, name_en, slug, description, icon, display_order, estimated_minutes, learning_objectives, content_strategy, feature_tags) VALUES

-- Freshservice 커리큘럼
('freshservice', 'module', '티켓 관리 기초', 'Ticket Management Basics', 'ticket-basics',
 'IT 서비스 요청을 티켓으로 관리하는 기본 개념과 워크플로우를 학습합니다.',
 'fa-ticket-alt', 1, 30,
 '["티켓의 개념과 생명주기 이해", "우선순위와 상태 관리", "담당자 배정 방법", "SLA 기초"]'::jsonb,
 'db_only',
 ARRAY['ticketing', 'sla', 'assignment']),

('freshservice', 'module', '서비스 카탈로그', 'Service Catalog', 'service-catalog',
 '사용자에게 제공할 IT 서비스를 카탈로그로 구성하고 관리하는 방법을 학습합니다.',
 'fa-book-open', 2, 25,
 '["서비스 카탈로그 개념", "서비스 항목 구성", "승인 워크플로우", "사용자 셀프서비스"]'::jsonb,
 'db_only',
 ARRAY['service_catalog', 'self_service', 'approval']),

('freshservice', 'module', '자동화 및 워크플로우', 'Automation & Workflow', 'automation',
 '반복 작업을 자동화하고 효율적인 워크플로우를 설계하는 방법을 학습합니다.',
 'fa-cogs', 3, 35,
 '["자동화 규칙 생성", "워크플로우 오토메이터", "시나리오 자동화", "SLA 자동화"]'::jsonb,
 'db_only',
 ARRAY['automation', 'workflow', 'scenario']),

('freshservice', 'module', '자산 관리 (CMDB)', 'Asset Management (CMDB)', 'asset-cmdb',
 'IT 자산과 구성 항목을 중앙에서 관리하고 추적하는 방법을 학습합니다.',
 'fa-server', 4, 40,
 '["자산 생명주기 관리", "CMDB 구성", "자산과 티켓 연결", "자산 검색"]'::jsonb,
 'db_only',
 ARRAY['asset_management', 'cmdb', 'discovery']),

('freshservice', 'module', '리포팅 및 분석', 'Reporting & Analytics', 'reporting',
 '서비스 데스크 성과를 측정하고 분석하는 방법을 학습합니다.',
 'fa-chart-bar', 5, 25,
 '["기본 보고서 활용", "커스텀 리포트 생성", "대시보드 구성", "KPI 분석"]'::jsonb,
 'db_only',
 ARRAY['reporting', 'analytics', 'dashboard']),

-- Freshdesk Omni 커리큘럼 (번들 전용)
('freshdesk_omni', 'bundle', 'Omni 통합 워크스페이스', 'Omni Unified Workspace', 'omni-workspace',
 'Freshdesk Omni의 통합 워크스페이스 개념과 활용법을 학습합니다.',
 'fa-layer-group', 1, 25,
 '["통합 워크스페이스 이해", "채널 통합 뷰", "에이전트 경험", "컨텍스트 보존"]'::jsonb,
 'hybrid',
 ARRAY['unified_workspace', 'omnichannel']),

('freshdesk_omni', 'bundle', '채팅-티켓 전환 플로우', 'Chat to Ticket Flow', 'chat-to-ticket',
 'Freshchat 대화를 Freshdesk 티켓으로 전환하는 프로세스를 학습합니다.',
 'fa-exchange-alt', 2, 20,
 '["대화 → 티켓 전환", "컨텍스트 보존", "자동 전환 규칙", "에스컬레이션"]'::jsonb,
 'hybrid',
 ARRAY['conversation_to_ticket', 'escalation']),

-- Freshsales 커리큘럼
('freshsales', 'module', 'CRM 기초', 'CRM Basics', 'crm-basics',
 'Freshsales CRM의 기본 개념과 리드/연락처 관리를 학습합니다.',
 'fa-users', 1, 30,
 '["CRM 개념 이해", "리드 vs 연락처", "계정 관리", "데이터 임포트"]'::jsonb,
 'hybrid',
 ARRAY['crm', 'lead', 'contact']),

('freshsales', 'module', '영업 파이프라인', 'Sales Pipeline', 'sales-pipeline',
 '딜 관리와 영업 파이프라인 최적화 방법을 학습합니다.',
 'fa-funnel-dollar', 2, 35,
 '["파이프라인 구성", "딜 스테이지 관리", "예측 및 분석", "영업 프로세스"]'::jsonb,
 'hybrid',
 ARRAY['pipeline', 'deal', 'forecast']),

-- Freshsales → Omni 애드온 시나리오
('freshsales', 'addon', 'Freshsales + Omni 통합', 'Freshsales Omni Integration', 'freshsales-omni-integration',
 'Freshsales를 Freshdesk Omni에 애드온으로 연동하는 방법을 학습합니다.',
 'fa-plug', 10, 30,
 '["애드온 설정 방법", "CRM-티켓 연동", "고객 컨텍스트 공유", "딜 정보 활용"]'::jsonb,
 'hybrid',
 ARRAY['addon', 'integration', 'crm_sync']),

-- Freshdesk 커리큘럼 (단독)
('freshdesk', 'module', '티켓 관리 기초', 'Ticket Management Basics', 'ticket-basics',
 '고객 문의를 티켓으로 관리하는 기본 개념과 워크플로우를 학습합니다.',
 'fa-ticket-alt', 1, 30,
 '["티켓 생성 및 분류", "우선순위 관리", "담당자 배정", "상태 관리"]'::jsonb,
 'hybrid',
 ARRAY['ticketing', 'priority', 'assignment']),

('freshdesk', 'module', '옴니채널 지원', 'Omnichannel Support', 'omnichannel',
 '이메일, 전화, 소셜 미디어 등 다양한 채널의 문의를 통합 관리합니다.',
 'fa-globe', 2, 25,
 '["채널 설정", "이메일 연동", "소셜 미디어 연동", "전화 연동"]'::jsonb,
 'hybrid',
 ARRAY['omnichannel', 'email', 'social']),

-- Freshchat 커리큘럼
('freshchat', 'module', '실시간 채팅 설정', 'Live Chat Setup', 'live-chat-setup',
 'Freshchat 위젯을 설치하고 실시간 채팅을 설정하는 방법을 학습합니다.',
 'fa-comments', 1, 20,
 '["위젯 설치", "채팅 설정", "근무 시간 설정", "환영 메시지"]'::jsonb,
 'hybrid',
 ARRAY['live_chat', 'widget', 'setup']),

('freshchat', 'module', '챗봇 구성', 'Chatbot Configuration', 'chatbot',
 'Freddy AI 챗봇을 구성하고 자동 응답을 설정하는 방법을 학습합니다.',
 'fa-robot', 2, 30,
 '["챗봇 플로우 설계", "FAQ 연동", "자동 응답 규칙", "핸드오프 설정"]'::jsonb,
 'hybrid',
 ARRAY['chatbot', 'freddy', 'automation'])

ON CONFLICT (target_product_id, slug) DO UPDATE SET
    name_ko = EXCLUDED.name_ko,
    name_en = EXCLUDED.name_en,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon,
    display_order = EXCLUDED.display_order,
    estimated_minutes = EXCLUDED.estimated_minutes,
    learning_objectives = EXCLUDED.learning_objectives,
    content_strategy = EXCLUDED.content_strategy,
    feature_tags = EXCLUDED.feature_tags,
    updated_at = NOW();

-- ============================================
-- 뷰: 제품별 학습 경로 조회
-- ============================================
CREATE OR REPLACE VIEW v_product_curriculum AS
SELECT 
    cm.id AS module_id,
    cm.target_product_id,
    cm.target_product_type,
    cm.name_ko AS module_name,
    cm.slug,
    cm.description,
    cm.display_order,
    cm.estimated_minutes,
    cm.feature_tags,
    CASE 
        WHEN cm.target_product_type = 'module' THEN pm.name_ko
        WHEN cm.target_product_type = 'bundle' THEN pb.name_ko
        ELSE cm.target_product_id
    END AS product_name,
    CASE 
        WHEN cm.target_product_type = 'module' THEN pm.domain
        ELSE NULL
    END AS product_domain
FROM curriculum_modules cm
LEFT JOIN product_modules pm ON cm.target_product_id = pm.id AND cm.target_product_type = 'module'
LEFT JOIN product_bundles pb ON cm.target_product_id = pb.id AND cm.target_product_type = 'bundle'
WHERE cm.is_active = true
ORDER BY cm.target_product_id, cm.display_order;

COMMENT ON VIEW v_product_curriculum IS '제품별 학습 커리큘럼 통합 뷰';

-- ============================================
-- 뷰: 번들 구성 상세
-- ============================================
CREATE OR REPLACE VIEW v_bundle_composition AS
SELECT 
    pb.id AS bundle_id,
    pb.name_ko AS bundle_name,
    pb.integration_type,
    pb.workspace_type,
    pm.id AS module_id,
    pm.name_ko AS module_name,
    pm.domain AS module_domain,
    pm.capabilities AS module_capabilities
FROM product_bundles pb
CROSS JOIN LATERAL unnest(pb.base_module_ids) AS module_id_text
JOIN product_modules pm ON pm.id = module_id_text
WHERE pb.is_active = true AND pm.is_active = true;

COMMENT ON VIEW v_bundle_composition IS '번들 구성 모듈 상세 뷰';

-- ============================================
-- 확인 쿼리
-- ============================================
-- SELECT * FROM product_modules;
-- SELECT * FROM product_bundles;
-- SELECT * FROM product_relationships;
-- SELECT * FROM curriculum_modules ORDER BY target_product_id, display_order;
-- SELECT * FROM v_product_curriculum;
-- SELECT * FROM v_bundle_composition;
