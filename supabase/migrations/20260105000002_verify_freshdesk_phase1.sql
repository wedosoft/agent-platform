-- ============================================
-- Freshdesk Phase1 마이그레이션 검증
-- Date: 2026-01-05
-- Purpose: 삽입된 데이터 검증 (모듈, 섹션, 퀴즈 수 확인)
-- ============================================

-- ============================================
-- 1. 모듈 수 확인 (4개여야 함)
-- ============================================
DO $$
DECLARE
    module_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO module_count 
    FROM onboarding.curriculum_modules 
    WHERE target_product_id = 'freshdesk' 
      AND is_active = true;
    
    IF module_count = 4 THEN
        RAISE NOTICE '✅ 모듈 수 확인: %개 (예상: 4개)', module_count;
    ELSE
        RAISE WARNING '⚠️ 모듈 수 불일치: %개 (예상: 4개)', module_count;
    END IF;
END $$;

-- ============================================
-- 2. 모듈 목록 및 기본 정보 확인
-- ============================================
SELECT 
    cm.name_ko,
    cm.slug,
    cm.display_order,
    cm.estimated_minutes,
    cm.id
FROM onboarding.curriculum_modules cm
WHERE cm.target_product_id = 'freshdesk' 
  AND cm.is_active = true
ORDER BY cm.display_order;

-- ============================================
-- 3. 총 섹션 개수 확인
-- ============================================
DO $$
DECLARE
    section_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO section_count 
    FROM onboarding.module_contents mc
    JOIN onboarding.curriculum_modules cm ON mc.module_id = cm.id
    WHERE cm.target_product_id = 'freshdesk'
      AND cm.is_active = true
      AND mc.is_active = true;
    
    RAISE NOTICE '섹션 콘텐츠 총 개수: %개 (예상: 28~32개)', section_count;
END $$;

-- ============================================
-- 4. 모듈별 섹션 개수
-- ============================================
SELECT 
    cm.name_ko,
    cm.display_order,
    COUNT(mc.id) as section_count
FROM onboarding.curriculum_modules cm
LEFT JOIN onboarding.module_contents mc ON cm.id = mc.module_id AND mc.is_active = true
WHERE cm.target_product_id = 'freshdesk' 
  AND cm.is_active = true
GROUP BY cm.id, cm.name_ko, cm.display_order
ORDER BY cm.display_order;

-- ============================================
-- 5. 모듈별 퀴즈 개수
-- ============================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'onboarding' 
        AND table_name = 'quiz_questions'
    ) THEN
        PERFORM 1;  -- 테이블 존재 확인용
    ELSE
        RAISE NOTICE 'quiz_questions 테이블이 존재하지 않습니다. 퀴즈 검증을 건너뜁니다.';
        RETURN;
    END IF;
END $$;

SELECT 
    cm.name_ko,
    cm.display_order,
    COUNT(qq.id) as quiz_count
FROM onboarding.curriculum_modules cm
LEFT JOIN onboarding.quiz_questions qq ON cm.id = qq.module_id AND qq.is_active = true
WHERE cm.target_product_id = 'freshdesk' 
  AND cm.is_active = true
GROUP BY cm.id, cm.name_ko, cm.display_order
ORDER BY cm.display_order;

-- ============================================
-- 6. 총 퀴즈 개수 확인
-- ============================================
DO $$
DECLARE
    quiz_count INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'onboarding' 
        AND table_name = 'quiz_questions'
    ) THEN
        SELECT COUNT(*) INTO quiz_count 
        FROM onboarding.quiz_questions qq
        JOIN onboarding.curriculum_modules cm ON qq.module_id = cm.id
        WHERE cm.target_product_id = 'freshdesk'
          AND cm.is_active = true
          AND qq.is_active = true;
        
        RAISE NOTICE '퀴즈 총 개수: %개 (예상: 모듈 1~2 각 3개씩, 총 6개 이상)', quiz_count;
    ELSE
        RAISE NOTICE 'quiz_questions 테이블이 없어 퀴즈 검증을 건너뜁니다.';
    END IF;
END $$;

-- ============================================
-- 7. 외래 키 무결성 확인 (고아 레코드 체크)
-- ============================================

-- module_contents에서 존재하지 않는 module_id 참조
SELECT 
    'module_contents 고아 레코드' as check_type,
    COUNT(*) as orphan_count
FROM onboarding.module_contents mc
LEFT JOIN onboarding.curriculum_modules cm ON mc.module_id = cm.id
WHERE cm.id IS NULL;

-- quiz_questions에서 존재하지 않는 module_id 참조
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'onboarding' 
        AND table_name = 'quiz_questions'
    ) THEN
        SELECT COUNT(*) INTO orphan_count 
        FROM onboarding.quiz_questions qq
        LEFT JOIN onboarding.curriculum_modules cm ON qq.module_id = cm.id
        WHERE cm.id IS NULL;
        
        IF orphan_count = 0 THEN
            RAISE NOTICE '✅ quiz_questions 외래 키 무결성: OK';
        ELSE
            RAISE WARNING '⚠️ quiz_questions 고아 레코드: %개', orphan_count;
        END IF;
    END IF;
END $$;

-- ============================================
-- 8. slug 중복 확인
-- ============================================
SELECT 
    slug,
    COUNT(*) as count
FROM onboarding.curriculum_modules
WHERE target_product_id = 'freshdesk' 
  AND is_active = true
GROUP BY slug
HAVING COUNT(*) > 1;

-- ============================================
-- 9. 필수 필드 누락 확인
-- ============================================
SELECT 
    '모듈 필수 필드 누락' as check_type,
    COUNT(*) as missing_count
FROM onboarding.curriculum_modules
WHERE target_product_id = 'freshdesk' 
  AND is_active = true
  AND (name_ko IS NULL OR name_ko = '' OR slug IS NULL OR slug = '');

-- ============================================
-- 10. 섹션 타입 분포 확인
-- ============================================
SELECT 
    mc.section_type,
    COUNT(*) as count
FROM onboarding.module_contents mc
JOIN onboarding.curriculum_modules cm ON mc.module_id = cm.id
WHERE cm.target_product_id = 'freshdesk' 
  AND cm.is_active = true
  AND mc.is_active = true
GROUP BY mc.section_type
ORDER BY count DESC;

-- ============================================
-- 검증 완료 메시지
-- ============================================
DO $$
BEGIN
    RAISE NOTICE '✅ 검증 쿼리 실행 완료. 위 결과를 확인하세요.';
END $$;

