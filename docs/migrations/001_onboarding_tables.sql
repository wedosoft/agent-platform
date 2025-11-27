-- ============================================
-- 온보딩 진행도 영속화를 위한 Supabase 테이블 생성
-- 실행: Supabase Dashboard > SQL Editor
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

    -- 복합 유니크 제약 (같은 세션에서 같은 시나리오는 1번만)
    CONSTRAINT unique_session_scenario UNIQUE (session_id, scenario_id)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_session_id
    ON onboarding_progress(session_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_scenario_id
    ON onboarding_progress(scenario_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_completed_at
    ON onboarding_progress(completed_at DESC);

-- 3. updated_at 자동 업데이트 트리거 (세션 테이블)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_onboarding_sessions_updated_at
    BEFORE UPDATE ON onboarding_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- RLS (Row Level Security) 정책 (선택사항)
-- 필요시 활성화
-- ============================================

-- ALTER TABLE onboarding_sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE onboarding_progress ENABLE ROW LEVEL SECURITY;

-- 서비스 역할 키로 모든 작업 허용
-- CREATE POLICY "Service role can do everything on onboarding_sessions"
--     ON onboarding_sessions
--     FOR ALL
--     USING (true)
--     WITH CHECK (true);

-- CREATE POLICY "Service role can do everything on onboarding_progress"
--     ON onboarding_progress
--     FOR ALL
--     USING (true)
--     WITH CHECK (true);

-- ============================================
-- 확인 쿼리
-- ============================================

-- 테이블 확인
-- SELECT * FROM onboarding_sessions LIMIT 5;
-- SELECT * FROM onboarding_progress LIMIT 5;

-- 세션별 진행도 확인
-- SELECT
--     s.session_id,
--     s.user_name,
--     COUNT(p.id) as completed_count,
--     ROUND(COUNT(p.id)::numeric / 12 * 100, 1) as completion_rate
-- FROM onboarding_sessions s
-- LEFT JOIN onboarding_progress p ON s.session_id = p.session_id
-- GROUP BY s.session_id, s.user_name
-- ORDER BY s.created_at DESC;
