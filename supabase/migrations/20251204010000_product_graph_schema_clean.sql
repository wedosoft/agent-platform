-- ============================================
-- Freshworks 제품 그래프 스키마 (Clean Install)
-- Date: 2025-12-04
-- Description: 기존 테이블 삭제 후 재생성
-- ============================================

-- ============================================
-- 기존 테이블 삭제 (CASCADE로 종속 객체도 삭제)
-- ============================================
DROP VIEW IF EXISTS v_bundle_composition CASCADE;
DROP VIEW IF EXISTS v_product_curriculum CASCADE;
DROP TABLE IF EXISTS module_progress CASCADE;
DROP TABLE IF EXISTS curriculum_modules CASCADE;
DROP TABLE IF EXISTS addon_configurations CASCADE;
DROP TABLE IF EXISTS product_relationships CASCADE;
DROP TABLE IF EXISTS product_bundles CASCADE;
DROP TABLE IF EXISTS product_modules CASCADE;

-- ============================================
-- 1. Product Modules (독립 제품 모듈)
-- ============================================
CREATE TABLE product_modules (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    freddy_ai_enabled BOOLEAN DEFAULT false,
    capabilities JSONB NOT NULL DEFAULT '[]',
    rag_product_keys TEXT[] NOT NULL DEFAULT '{}',
    logo_url TEXT,
    icon VARCHAR(50),
    color_primary VARCHAR(20),
    description TEXT,
    description_ko TEXT,
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_product_modules_domain ON product_modules(domain);
CREATE INDEX idx_product_modules_active ON product_modules(is_active) WHERE is_active = true;

-- ============================================
-- 2. Product Bundles (통합 번들)
-- ============================================
CREATE TABLE product_bundles (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100) NOT NULL,
    base_module_ids TEXT[] NOT NULL,
    integration_type VARCHAR(30) NOT NULL,
    workspace_type VARCHAR(20) NOT NULL,
    rag_product_keys TEXT[] NOT NULL DEFAULT '{}',
    integration_features JSONB,
    pricing_advantage_percent DECIMAL(5,2) DEFAULT 0,
    description TEXT,
    description_ko TEXT,
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_product_bundles_active ON product_bundles(is_active) WHERE is_active = true;

-- ============================================
-- 3. Product Relationships (제품 관계 그래프)
-- ============================================
CREATE TABLE product_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(50) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    target_id VARCHAR(50) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    relationship_type VARCHAR(30) NOT NULL,
    bidirectional BOOLEAN DEFAULT false,
    integration_characteristics JSONB,
    result_bundle_id VARCHAR(50) REFERENCES product_bundles(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_product_rel_source ON product_relationships(source_id, source_type);
CREATE INDEX idx_product_rel_target ON product_relationships(target_id, target_type);
CREATE INDEX idx_product_rel_type ON product_relationships(relationship_type);

-- ============================================
-- 4. Addon Configurations (애드온 제약 조건)
-- ============================================
CREATE TABLE addon_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    addon_module_id VARCHAR(50) NOT NULL REFERENCES product_modules(id),
    target_bundle_id VARCHAR(50) NOT NULL REFERENCES product_bundles(id),
    integration_depth VARCHAR(20) NOT NULL,
    constraints JSONB NOT NULL DEFAULT '[]',
    required_features TEXT[] DEFAULT '{}',
    recommended_settings JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_addon_config_addon ON addon_configurations(addon_module_id);
CREATE INDEX idx_addon_config_target ON addon_configurations(target_bundle_id);

-- ============================================
-- 5. Curriculum Modules (학습 커리큘럼)
-- ============================================
CREATE TABLE curriculum_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_product_id VARCHAR(50) NOT NULL,
    target_product_type VARCHAR(20) NOT NULL,
    name_ko VARCHAR(200) NOT NULL,
    name_en VARCHAR(200),
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    display_order INT DEFAULT 0,
    estimated_minutes INT DEFAULT 30,
    learning_objectives JSONB,
    content_strategy VARCHAR(20) DEFAULT 'hybrid',
    kb_category_slug VARCHAR(100),
    prerequisite_module_ids UUID[] DEFAULT '{}',
    feature_tags TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(target_product_id, slug)
);

CREATE INDEX idx_curriculum_modules_target ON curriculum_modules(target_product_id, target_product_type);
CREATE INDEX idx_curriculum_modules_slug ON curriculum_modules(slug);
CREATE INDEX idx_curriculum_modules_order ON curriculum_modules(target_product_id, display_order);
CREATE INDEX idx_curriculum_modules_active ON curriculum_modules(is_active) WHERE is_active = true;

-- ============================================
-- 6. Module Progress (학습 진도)
-- ============================================
CREATE TABLE module_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    module_id UUID NOT NULL REFERENCES curriculum_modules(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'not_started',
    learning_started_at TIMESTAMPTZ,
    learning_completed_at TIMESTAMPTZ,
    total_learning_seconds INT DEFAULT 0,
    quiz_score INT,
    quiz_attempts INT DEFAULT 0,
    quiz_passed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, module_id)
);

CREATE INDEX idx_module_progress_session ON module_progress(session_id);
CREATE INDEX idx_module_progress_module ON module_progress(module_id);
CREATE INDEX idx_module_progress_status ON module_progress(status);

-- ============================================
-- 초기 데이터: 제품 모듈
-- ============================================
INSERT INTO product_modules (id, name, name_ko, domain, freddy_ai_enabled, capabilities, rag_product_keys, description_ko, display_order) VALUES
('freshdesk', 'Freshdesk', 'Freshdesk', 'customer_service', true,
 '[{"id": "ticketing", "name": "티켓 관리", "core": true}, {"id": "knowledge_base", "name": "지식 베이스", "core": true}, {"id": "automation", "name": "자동화", "core": false}]'::jsonb,
 ARRAY['freshdesk', 'fd'], '옴니채널 고객 지원 플랫폼', 1),
('freshchat', 'Freshchat', 'Freshchat', 'customer_service', true,
 '[{"id": "live_chat", "name": "실시간 채팅", "core": true}, {"id": "chatbot", "name": "챗봇", "core": true}]'::jsonb,
 ARRAY['freshchat', 'fc'], '모던 메시징 솔루션', 2),
('freshsales', 'Freshsales', 'Freshsales', 'sales_marketing', true,
 '[{"id": "crm", "name": "CRM", "core": true}, {"id": "pipeline", "name": "영업 파이프라인", "core": true}]'::jsonb,
 ARRAY['freshsales', 'fs'], 'AI 기반 CRM 플랫폼', 3),
('freshservice', 'Freshservice', 'Freshservice', 'itsm', true,
 '[{"id": "ticketing", "name": "티켓 관리", "core": true}, {"id": "asset_management", "name": "자산 관리", "core": true}, {"id": "cmdb", "name": "CMDB", "core": true}]'::jsonb,
 ARRAY['freshservice', 'fsvc'], 'IT 서비스 관리(ITSM) 플랫폼', 4);

-- ============================================
-- 초기 데이터: 번들
-- ============================================
INSERT INTO product_bundles (id, name, name_ko, base_module_ids, integration_type, workspace_type, rag_product_keys, integration_features, pricing_advantage_percent, description_ko, display_order) VALUES
('freshdesk_omni', 'Freshdesk Omni', 'Freshdesk Omni', 
 ARRAY['freshdesk', 'freshchat'], 'native_unified', 'unified',
 ARRAY['freshdesk-omni', 'omni', 'fdo'],
 '{"unified_inbox": true, "shared_contacts": true, "conversation_to_ticket": true}'::jsonb,
 20.00, 'Freshdesk + Freshchat 통합 번들', 1);

-- ============================================
-- 초기 데이터: 제품 관계
-- ============================================
INSERT INTO product_relationships (source_id, source_type, target_id, target_type, relationship_type, result_bundle_id, integration_characteristics) VALUES
('freshdesk', 'module', 'freshchat', 'module', 'bundles_with', 'freshdesk_omni',
 '{"conversation_to_ticket": true, "shared_contact_db": true}'::jsonb),
('freshchat', 'module', 'freshdesk_omni', 'bundle', 'included_in', NULL, NULL),
('freshsales', 'module', 'freshdesk_omni', 'bundle', 'addon_to', NULL,
 '{"crm_sync": true, "contact_enrichment": true}'::jsonb);

-- ============================================
-- 초기 데이터: 애드온 설정
-- ============================================
INSERT INTO addon_configurations (addon_module_id, target_bundle_id, integration_depth, constraints, required_features) VALUES
('freshsales', 'freshdesk_omni', 'deep',
 '[{"type": "plan_matching", "required_plans": ["pro", "enterprise"]}]'::jsonb,
 ARRAY['crm_sync', 'contact_management']);

-- ============================================
-- 초기 데이터: 커리큘럼 모듈
-- ============================================
INSERT INTO curriculum_modules (target_product_id, target_product_type, name_ko, name_en, slug, description, icon, display_order, estimated_minutes, feature_tags) VALUES
-- Freshservice
('freshservice', 'module', '티켓 관리 기초', 'Ticket Management Basics', 'ticket-basics', 'IT 서비스 요청을 티켓으로 관리하는 기본 워크플로우', 'fa-ticket-alt', 1, 30, ARRAY['ticketing', 'sla']),
('freshservice', 'module', '서비스 카탈로그', 'Service Catalog', 'service-catalog', 'IT 서비스를 카탈로그로 구성하고 관리', 'fa-book-open', 2, 25, ARRAY['service_catalog']),
('freshservice', 'module', '자동화 및 워크플로우', 'Automation & Workflow', 'automation', '반복 작업을 자동화하는 방법', 'fa-cogs', 3, 35, ARRAY['automation', 'workflow']),
('freshservice', 'module', '자산 관리 (CMDB)', 'Asset Management', 'asset-cmdb', 'IT 자산과 구성 항목 관리', 'fa-server', 4, 40, ARRAY['asset_management', 'cmdb']),
('freshservice', 'module', '리포팅 및 분석', 'Reporting & Analytics', 'reporting', '서비스 데스크 성과 측정', 'fa-chart-bar', 5, 25, ARRAY['reporting']),
-- Freshdesk Omni (번들)
('freshdesk_omni', 'bundle', 'Omni 통합 워크스페이스', 'Omni Unified Workspace', 'omni-workspace', '통합 워크스페이스 개념과 활용법', 'fa-layer-group', 1, 25, ARRAY['unified_workspace']),
('freshdesk_omni', 'bundle', '채팅-티켓 전환 플로우', 'Chat to Ticket Flow', 'chat-to-ticket', '채팅을 티켓으로 전환하는 프로세스', 'fa-exchange-alt', 2, 20, ARRAY['conversation_to_ticket']),
-- Freshsales
('freshsales', 'module', 'CRM 기초', 'CRM Basics', 'crm-basics', 'CRM 기본 개념과 리드/연락처 관리', 'fa-users', 1, 30, ARRAY['crm', 'lead']),
('freshsales', 'module', '영업 파이프라인', 'Sales Pipeline', 'sales-pipeline', '딜 관리와 영업 파이프라인 최적화', 'fa-funnel-dollar', 2, 35, ARRAY['pipeline', 'deal']),
('freshsales', 'addon', 'Freshsales + Omni 통합', 'Freshsales Omni Integration', 'freshsales-omni-integration', 'Freshsales를 Omni에 애드온 연동', 'fa-plug', 10, 30, ARRAY['addon', 'integration']),
-- Freshdesk
('freshdesk', 'module', '티켓 관리 기초', 'Ticket Management Basics', 'ticket-basics', '고객 문의를 티켓으로 관리하는 기본 워크플로우', 'fa-ticket-alt', 1, 30, ARRAY['ticketing']),
('freshdesk', 'module', '옴니채널 지원', 'Omnichannel Support', 'omnichannel', '다양한 채널의 문의를 통합 관리', 'fa-globe', 2, 25, ARRAY['omnichannel']),
-- Freshchat
('freshchat', 'module', '실시간 채팅 설정', 'Live Chat Setup', 'live-chat-setup', 'Freshchat 위젯 설치와 설정', 'fa-comments', 1, 20, ARRAY['live_chat']),
('freshchat', 'module', '챗봇 구성', 'Chatbot Configuration', 'chatbot', 'Freddy AI 챗봇 구성과 자동 응답', 'fa-robot', 2, 30, ARRAY['chatbot', 'freddy']);

-- ============================================
-- 뷰: 제품별 학습 경로 조회
-- ============================================
CREATE VIEW v_product_curriculum AS
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
    END AS product_name
FROM curriculum_modules cm
LEFT JOIN product_modules pm ON cm.target_product_id = pm.id AND cm.target_product_type = 'module'
LEFT JOIN product_bundles pb ON cm.target_product_id = pb.id AND cm.target_product_type = 'bundle'
WHERE cm.is_active = true
ORDER BY cm.target_product_id, cm.display_order;

-- ============================================
-- 뷰: 번들 구성 상세
-- ============================================
CREATE VIEW v_bundle_composition AS
SELECT 
    pb.id AS bundle_id,
    pb.name_ko AS bundle_name,
    pb.integration_type,
    pm.id AS module_id,
    pm.name_ko AS module_name,
    pm.domain AS module_domain
FROM product_bundles pb
CROSS JOIN LATERAL unnest(pb.base_module_ids) AS module_id_text
JOIN product_modules pm ON pm.id = module_id_text
WHERE pb.is_active = true AND pm.is_active = true;

-- ============================================
-- 완료!
-- ============================================
SELECT 'Schema created successfully!' AS status;
SELECT COUNT(*) AS product_modules_count FROM product_modules;
SELECT COUNT(*) AS product_bundles_count FROM product_bundles;
SELECT COUNT(*) AS curriculum_modules_count FROM curriculum_modules;
