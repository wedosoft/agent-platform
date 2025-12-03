-- ============================================
-- Seed: Freshservice Core Curriculum Modules
-- Date: 2025-12-03
-- Description: 3개 Core 모듈 (티켓 관리, 서비스 카탈로그, SLA 관리)
-- ============================================

-- ============================================
-- 1. Core 모듈 INSERT
-- ============================================
INSERT INTO curriculum_modules (
    id,
    product,
    name_ko,
    name_en,
    slug,
    description,
    icon,
    estimated_minutes,
    display_order,
    is_active,
    kb_category_slug,
    prerequisites
) VALUES 
-- 모듈 1: 티켓 관리
(
    'a1b2c3d4-0001-4000-8000-000000000001',
    'freshservice',
    '티켓 관리',
    'Ticket Management',
    'ticket-management',
    'IT 서비스 데스크의 핵심인 티켓 생성, 분류, 할당, 추적, 해결 과정을 학습합니다. 티켓 워크플로우, 자동화 규칙, 에스컬레이션 정책을 이해하고 효율적인 티켓 관리 방법을 익힙니다.',
    'ticket',
    45,
    1,
    true,
    'support-guide-it-service-management',
    NULL
),
-- 모듈 2: 서비스 카탈로그
(
    'a1b2c3d4-0002-4000-8000-000000000002',
    'freshservice',
    '서비스 카탈로그',
    'Service Catalog',
    'service-catalog',
    '사용자가 IT 서비스를 요청할 수 있는 셀프 서비스 포털을 구축하고 관리하는 방법을 학습합니다. 서비스 항목 생성, 승인 워크플로우, 서비스 요청 자동화를 다룹니다.',
    'catalog',
    40,
    2,
    true,
    'support-guide-it-service-management',
    ARRAY['a1b2c3d4-0001-4000-8000-000000000001']::UUID[]
),
-- 모듈 3: SLA 관리
(
    'a1b2c3d4-0003-4000-8000-000000000003',
    'freshservice',
    'SLA 관리',
    'SLA Management',
    'sla-management',
    '서비스 수준 계약(SLA)을 정의하고 모니터링하는 방법을 학습합니다. SLA 정책 설정, 응답/해결 시간 목표, 에스컬레이션 규칙, SLA 준수율 보고서를 다룹니다.',
    'clock',
    35,
    3,
    true,
    'support-guide-it-service-management',
    ARRAY['a1b2c3d4-0001-4000-8000-000000000001']::UUID[]
);

-- ============================================
-- 2. 확인 쿼리
-- ============================================
-- SELECT * FROM curriculum_modules WHERE product = 'freshservice' ORDER BY display_order;
