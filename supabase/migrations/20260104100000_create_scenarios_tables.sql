-- ============================================
-- 시나리오 테이블 생성 (constants.ts에서 마이그레이션)
-- Date: 2026-01-04
-- Description: 하드코딩된 시나리오를 DB로 마이그레이션하여 CMS에서 관리 가능하도록 함
-- ============================================

-- 1. 시나리오 카테고리 테이블
CREATE TABLE IF NOT EXISTS onboarding.scenario_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_ko TEXT NOT NULL,
    icon TEXT,
    description TEXT,
    description_ko TEXT,
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 시나리오 테이블
CREATE TABLE IF NOT EXISTS onboarding.scenarios (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL REFERENCES onboarding.scenario_categories(id),
    title TEXT NOT NULL,
    title_ko TEXT NOT NULL,
    icon TEXT,
    description TEXT NOT NULL,
    description_ko TEXT NOT NULL,
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 시나리오 선택지 테이블
CREATE TABLE IF NOT EXISTS onboarding.scenario_choices (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES onboarding.scenarios(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    text_ko TEXT NOT NULL,
    display_order INT DEFAULT 0,
    is_recommended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_scenarios_category_id ON onboarding.scenarios(category_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_display_order ON onboarding.scenarios(display_order);
CREATE INDEX IF NOT EXISTS idx_scenarios_is_active ON onboarding.scenarios(is_active);
CREATE INDEX IF NOT EXISTS idx_scenario_choices_scenario_id ON onboarding.scenario_choices(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenario_choices_display_order ON onboarding.scenario_choices(display_order);

-- 테이블 설명
COMMENT ON TABLE onboarding.scenario_categories IS '시나리오 카테고리 (업무 관리, 커뮤니케이션, 문제 해결 등)';
COMMENT ON TABLE onboarding.scenarios IS '온보딩 시나리오 (상황 기반 학습 콘텐츠)';
COMMENT ON TABLE onboarding.scenario_choices IS '시나리오별 선택지';
COMMENT ON COLUMN onboarding.scenario_choices.is_recommended IS '추천 선택지 여부 (피드백에서 활용)';

-- RLS 정책 설정
ALTER TABLE onboarding.scenario_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding.scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding.scenario_choices ENABLE ROW LEVEL SECURITY;

-- 읽기 정책 (모든 사용자)
CREATE POLICY "scenario_categories_read_policy" ON onboarding.scenario_categories
    FOR SELECT USING (true);

CREATE POLICY "scenarios_read_policy" ON onboarding.scenarios
    FOR SELECT USING (true);

CREATE POLICY "scenario_choices_read_policy" ON onboarding.scenario_choices
    FOR SELECT USING (true);

-- 쓰기 정책 (service_role만)
CREATE POLICY "scenario_categories_write_policy" ON onboarding.scenario_categories
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "scenarios_write_policy" ON onboarding.scenarios
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "scenario_choices_write_policy" ON onboarding.scenario_choices
    FOR ALL USING (auth.role() = 'service_role');

-- service_role 권한 부여
GRANT ALL ON onboarding.scenario_categories TO service_role;
GRANT ALL ON onboarding.scenarios TO service_role;
GRANT ALL ON onboarding.scenario_choices TO service_role;

-- anon 읽기 권한
GRANT SELECT ON onboarding.scenario_categories TO anon;
GRANT SELECT ON onboarding.scenarios TO anon;
GRANT SELECT ON onboarding.scenario_choices TO anon;
