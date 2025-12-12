-- ============================================
-- knowledge_articles 테이블 권한 부여
-- Date: 2025-12-12
-- Description: service_role이 knowledge_articles 테이블에 접근할 수 있도록 권한 부여
-- ============================================

-- service_role에 모든 권한 부여
GRANT ALL ON TABLE onboarding.knowledge_articles TO service_role;
GRANT ALL ON TABLE onboarding.knowledge_articles TO postgres;

-- RLS 비활성화 (service_role은 RLS를 우회함)
ALTER TABLE onboarding.knowledge_articles ENABLE ROW LEVEL SECURITY;

-- service_role은 모든 작업 허용 (RLS 우회)
CREATE POLICY "Service role can do everything"
ON onboarding.knowledge_articles
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- 익명 사용자도 읽기 가능 (선택사항 - 필요시 주석 해제)
-- CREATE POLICY "Anyone can read knowledge articles"
-- ON onboarding.knowledge_articles
-- FOR SELECT
-- TO anon
-- USING (true);
