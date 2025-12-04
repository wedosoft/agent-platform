-- ============================================
-- 온보딩 진행도 영속화를 위한 Supabase 테이블 생성
-- Date: 2024-12-04
-- ============================================

-- 1. 온보딩 세션 테이블
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    user_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_onboarding_sessions_session_id
    ON onboarding_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_sessions_created_at
    ON onboarding_sessions(created_at DESC);

-- 2. 온보딩 진행도 테이블
CREATE TABLE IF NOT EXISTS onboarding_progress (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    scenario_id TEXT NOT NULL,
    choice_id TEXT NOT NULL,
    feedback_rating INT,
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, scenario_id)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_session_id
    ON onboarding_progress(session_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_scenario_id
    ON onboarding_progress(scenario_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_completed_at
    ON onboarding_progress(completed_at DESC);

-- 코멘트
COMMENT ON TABLE onboarding_sessions IS '온보딩 세션 정보 (시나리오 학습)';
COMMENT ON TABLE onboarding_progress IS '시나리오별 진행도 추적';
COMMENT ON COLUMN onboarding_progress.feedback_rating IS '피드백 별점 (1-5)';
