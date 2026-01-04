-- ============================================
-- 대화 히스토리 테이블 생성 (인메모리 캐시 대체)
-- Date: 2026-01-04
-- Description: 서버 재시작 시에도 대화 히스토리를 유지하기 위한 영속화 테이블
-- ============================================

-- 1. 대화 히스토리 테이블
CREATE TABLE IF NOT EXISTS onboarding.chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 세션 정보
    session_id TEXT NOT NULL,
    context_type TEXT NOT NULL DEFAULT 'mentor', -- 'mentor', 'module', 'product'
    context_id TEXT, -- module_id 또는 product_id (컨텍스트별 대화 분리)
    
    -- 대화 내용
    role TEXT NOT NULL CHECK (role IN ('user', 'model')),
    content TEXT NOT NULL,
    
    -- 메타데이터
    turn_number INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 대화 요약 테이블 (긴 대화 압축용)
CREATE TABLE IF NOT EXISTS onboarding.chat_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 세션 정보
    session_id TEXT NOT NULL,
    context_type TEXT NOT NULL DEFAULT 'mentor',
    context_id TEXT,
    
    -- 요약 내용
    summary TEXT NOT NULL,
    summarized_turns INT NOT NULL DEFAULT 0, -- 요약된 턴 수
    last_turn_number INT NOT NULL DEFAULT 0, -- 마지막으로 요약된 턴 번호
    
    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON onboarding.chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_context ON onboarding.chat_history(session_id, context_type, context_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON onboarding.chat_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_turn ON onboarding.chat_history(session_id, context_type, context_id, turn_number);

CREATE INDEX IF NOT EXISTS idx_chat_summaries_session_id ON onboarding.chat_summaries(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_summaries_context ON onboarding.chat_summaries(session_id, context_type, context_id);

-- 테이블 설명
COMMENT ON TABLE onboarding.chat_history IS 'AI 멘토 대화 히스토리 (영속화)';
COMMENT ON COLUMN onboarding.chat_history.context_type IS '대화 컨텍스트 타입 (mentor: 일반 멘토, module: 모듈 학습, product: 제품 학습)';
COMMENT ON COLUMN onboarding.chat_history.context_id IS '컨텍스트별 ID (모듈 ID 또는 제품 ID)';
COMMENT ON COLUMN onboarding.chat_history.role IS '발화자 역할 (user: 사용자, model: AI)';
COMMENT ON COLUMN onboarding.chat_history.turn_number IS '대화 턴 번호 (순서 유지용)';

COMMENT ON TABLE onboarding.chat_summaries IS '긴 대화 요약 (10턴 이상 시 자동 생성)';
COMMENT ON COLUMN onboarding.chat_summaries.summarized_turns IS '요약에 포함된 턴 수';

-- RLS 정책 설정
ALTER TABLE onboarding.chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding.chat_summaries ENABLE ROW LEVEL SECURITY;

-- 읽기/쓰기 정책 (service_role만)
CREATE POLICY "chat_history_policy" ON onboarding.chat_history
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "chat_summaries_policy" ON onboarding.chat_summaries
    FOR ALL USING (auth.role() = 'service_role');

-- service_role 권한 부여
GRANT ALL ON onboarding.chat_history TO service_role;
GRANT ALL ON onboarding.chat_summaries TO service_role;

-- 대화 히스토리 자동 정리 함수 (10턴 초과 시 오래된 턴 삭제)
CREATE OR REPLACE FUNCTION onboarding.cleanup_old_chat_history()
RETURNS TRIGGER AS $$
DECLARE
    max_turns INT := 10;
    current_count INT;
BEGIN
    -- 현재 세션/컨텍스트의 턴 수 확인
    SELECT COUNT(*) INTO current_count
    FROM onboarding.chat_history
    WHERE session_id = NEW.session_id
      AND context_type = NEW.context_type
      AND COALESCE(context_id, '') = COALESCE(NEW.context_id, '');
    
    -- 최대 턴 수 초과 시 오래된 턴 삭제
    IF current_count > max_turns THEN
        DELETE FROM onboarding.chat_history
        WHERE id IN (
            SELECT id FROM onboarding.chat_history
            WHERE session_id = NEW.session_id
              AND context_type = NEW.context_type
              AND COALESCE(context_id, '') = COALESCE(NEW.context_id, '')
            ORDER BY turn_number ASC
            LIMIT (current_count - max_turns)
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 트리거 생성
DROP TRIGGER IF EXISTS trigger_cleanup_chat_history ON onboarding.chat_history;
CREATE TRIGGER trigger_cleanup_chat_history
    AFTER INSERT ON onboarding.chat_history
    FOR EACH ROW
    EXECUTE FUNCTION onboarding.cleanup_old_chat_history();
