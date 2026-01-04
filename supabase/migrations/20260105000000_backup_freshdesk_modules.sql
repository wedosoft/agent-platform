-- ============================================
-- Freshdesk 모듈 백업 (Phase1 대체 전)
-- Date: 2026-01-05
-- Purpose: 기존 Freshdesk 커리큘럼 데이터 백업 (롤백 대비)
-- ============================================

-- 1. 기존 모듈 백업
CREATE TABLE IF NOT EXISTS curriculum_modules_backup_20260105 AS 
SELECT * FROM onboarding.curriculum_modules 
WHERE target_product_id = 'freshdesk';

-- 백업 개수 확인
DO $$
DECLARE
    backup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO backup_count FROM curriculum_modules_backup_20260105;
    RAISE NOTICE '백업된 모듈 수: %', backup_count;
END $$;

-- 2. 기존 섹션 콘텐츠 백업
CREATE TABLE IF NOT EXISTS module_contents_backup_20260105 AS 
SELECT mc.* 
FROM onboarding.module_contents mc
WHERE mc.module_id IN (
    SELECT id FROM onboarding.curriculum_modules 
    WHERE target_product_id = 'freshdesk'
);

-- 백업 개수 확인
DO $$
DECLARE
    backup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO backup_count FROM module_contents_backup_20260105;
    RAISE NOTICE '백업된 섹션 콘텐츠 수: %', backup_count;
END $$;

-- 3. 기존 퀴즈 백업 (테이블이 존재하는 경우)
DO $$
DECLARE
    backup_count INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'onboarding' 
        AND table_name = 'quiz_questions'
    ) THEN
        EXECUTE 'CREATE TABLE IF NOT EXISTS quiz_questions_backup_20260105 AS 
                 SELECT qq.* 
                 FROM onboarding.quiz_questions qq
                 WHERE qq.module_id IN (
                     SELECT id FROM onboarding.curriculum_modules 
                     WHERE target_product_id = ''freshdesk''
                 )';
        
        EXECUTE 'SELECT COUNT(*) FROM quiz_questions_backup_20260105' INTO backup_count;
        RAISE NOTICE '백업된 퀴즈 수: %', backup_count;
    ELSE
        RAISE NOTICE 'quiz_questions 테이블이 존재하지 않습니다. 백업을 건너뜁니다.';
    END IF;
END $$;

-- 4. 사용자 진행 상태 확인 (경고용)
DO $$
DECLARE
    progress_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO progress_count 
    FROM onboarding.module_progress mp
    WHERE mp.module_id IN (
        SELECT id FROM onboarding.curriculum_modules 
        WHERE target_product_id = 'freshdesk'
    );
    
    IF progress_count > 0 THEN
        RAISE WARNING '기존 Freshdesk 모듈을 참조하는 진행 상태가 %건 있습니다. 삭제 시 해당 데이터도 영향을 받을 수 있습니다.', progress_count;
    ELSE
        RAISE NOTICE '기존 Freshdesk 모듈을 참조하는 진행 상태가 없습니다.';
    END IF;
END $$;

-- 5. 백업 완료 확인 쿼리 (수동 실행용)
-- SELECT 
--     (SELECT COUNT(*) FROM curriculum_modules_backup_20260105) as modules_backed_up,
--     (SELECT COUNT(*) FROM module_contents_backup_20260105) as contents_backed_up,
--     (SELECT COUNT(*) FROM quiz_questions_backup_20260105) as quizzes_backed_up;

