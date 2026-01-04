-- ============================================
-- 기존 Freshdesk 모듈 삭제 (Phase1 대체)
-- Date: 2026-01-05
-- Purpose: 기존 11개 Freshdesk 모듈 및 관련 데이터 삭제
-- Warning: 외래 키 순서 준수 필수 (자식 → 부모)
-- ============================================

-- 삭제 전 개수 확인
DO $$
DECLARE
    module_count INTEGER;
    content_count INTEGER;
    quiz_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO module_count 
    FROM onboarding.curriculum_modules 
    WHERE target_product_id = 'freshdesk';
    
    SELECT COUNT(*) INTO content_count 
    FROM onboarding.module_contents mc
    WHERE mc.module_id IN (
        SELECT id FROM onboarding.curriculum_modules 
        WHERE target_product_id = 'freshdesk'
    );
    
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'onboarding' 
        AND table_name = 'quiz_questions'
    ) THEN
        SELECT COUNT(*) INTO quiz_count 
        FROM onboarding.quiz_questions qq
        WHERE qq.module_id IN (
            SELECT id FROM onboarding.curriculum_modules 
            WHERE target_product_id = 'freshdesk'
        );
    ELSE
        quiz_count := 0;
    END IF;
    
    RAISE NOTICE '삭제 예정: 모듈 %개, 섹션 %개, 퀴즈 %개', module_count, content_count, quiz_count;
END $$;

-- ============================================
-- Step 1: 퀴즈 삭제 (자식 테이블)
-- ============================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'onboarding' 
        AND table_name = 'quiz_questions'
    ) THEN
        DELETE FROM onboarding.quiz_questions 
        WHERE module_id IN (
            SELECT id FROM onboarding.curriculum_modules 
            WHERE target_product_id = 'freshdesk'
        );
        RAISE NOTICE '퀴즈 삭제 완료';
    ELSE
        RAISE NOTICE 'quiz_questions 테이블이 없어 퀴즈 삭제를 건너뜁니다.';
    END IF;
END $$;

-- ============================================
-- Step 2: 섹션 콘텐츠 삭제 (자식 테이블)
-- ============================================
DELETE FROM onboarding.module_contents 
WHERE module_id IN (
    SELECT id FROM onboarding.curriculum_modules 
    WHERE target_product_id = 'freshdesk'
);

DO $$
DECLARE
    deleted_count INTEGER;
BEGIN
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '섹션 콘텐츠 삭제 완료: %건', deleted_count;
END $$;

-- ============================================
-- Step 3: 모듈 삭제 (부모 테이블)
-- ============================================
DELETE FROM onboarding.curriculum_modules 
WHERE target_product_id = 'freshdesk';

DO $$
DECLARE
    deleted_count INTEGER;
BEGIN
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '모듈 삭제 완료: %건', deleted_count;
END $$;

-- ============================================
-- 삭제 후 확인
-- ============================================
DO $$
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_count 
    FROM onboarding.curriculum_modules 
    WHERE target_product_id = 'freshdesk';
    
    IF remaining_count = 0 THEN
        RAISE NOTICE '✅ 모든 Freshdesk 모듈이 삭제되었습니다.';
    ELSE
        RAISE WARNING '⚠️ 아직 %개의 Freshdesk 모듈이 남아있습니다.', remaining_count;
    END IF;
END $$;

