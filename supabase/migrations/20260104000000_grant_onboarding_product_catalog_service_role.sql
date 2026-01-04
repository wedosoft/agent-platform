-- ============================================
-- 온보딩 제품 카탈로그 권한 보강 (service_role)
-- Date: 2026-01-04
-- Purpose:
--   - onboarding.product_modules / onboarding.product_bundles (table or view)에 대해
--     agent-platform 백엔드(service_role)가 조회 시 42501(permission denied) 발생하는 문제 해결
-- Notes:
--   - 기존 마이그레이션(20251217000000_fix_onboarding_product_catalog.sql)은 anon/authenticated만 GRANT 함
--   - 백엔드는 SUPABASE_COMMON_SERVICE_ROLE_KEY를 사용하므로 service_role 권한이 필요
-- ============================================

-- 1) 스키마 사용 권한
GRANT USAGE ON SCHEMA onboarding TO service_role;

-- 2) 명시적으로 제품 카탈로그 관계(테이블/뷰) SELECT 권한
GRANT SELECT ON TABLE onboarding.product_modules TO service_role;
GRANT SELECT ON TABLE onboarding.product_bundles TO service_role;

-- 3) 스키마 내 전체 테이블/뷰 SELECT 권한 (향후 확장 대비)
GRANT SELECT ON ALL TABLES IN SCHEMA onboarding TO service_role;

-- 4) (선택) onboarding 스키마에서 향후 생성되는 테이블/뷰 기본 권한 부여
--   - 마이그레이션 실행 주체(role)의 default privileges에 따라 효과가 달라질 수 있음
ALTER DEFAULT PRIVILEGES IN SCHEMA onboarding GRANT SELECT ON TABLES TO service_role;


