-- ============================================
-- 온보딩 제품 카탈로그 스키마 보강
-- Date: 2025-12-17
-- Purpose:
--   - agent-platform 백엔드가 schema='onboarding'로 product_modules/product_bundles를 조회할 때
--     PGRST205(스키마 캐시에서 테이블을 못 찾음)로 폴백되는 문제를 해결
-- Strategy:
--   1) onboarding 스키마 보장
--   2) public에 product_* 테이블이 있으면 onboarding에 VIEW로 노출
--   3) 둘 다 없으면 onboarding에 최소 테이블/시드 생성
-- ============================================

CREATE SCHEMA IF NOT EXISTS onboarding;

-- 1) onboarding.product_modules
DO $$
BEGIN
  IF to_regclass('onboarding.product_modules') IS NULL THEN
    IF to_regclass('public.product_modules') IS NOT NULL THEN
      EXECUTE 'CREATE VIEW onboarding.product_modules AS SELECT * FROM public.product_modules;';
    ELSE
      EXECUTE $DDL$
        CREATE TABLE IF NOT EXISTS onboarding.product_modules (
          id VARCHAR(50) PRIMARY KEY,
          name VARCHAR(100) NOT NULL,
          name_ko VARCHAR(100) NOT NULL,
          domain VARCHAR(50) NOT NULL,
          freddy_ai_enabled BOOLEAN DEFAULT false,
          capabilities JSONB NOT NULL DEFAULT '[]',
          rag_product_keys TEXT[] NOT NULL DEFAULT '{}',
          logo_url TEXT,
          icon VARCHAR(50),
          color_primary VARCHAR(20),
          description TEXT,
          description_ko TEXT,
          display_order INT DEFAULT 0,
          is_active BOOLEAN DEFAULT true,
          created_at TIMESTAMPTZ DEFAULT NOW(),
          updated_at TIMESTAMPTZ DEFAULT NOW()
        );
      $DDL$;

      EXECUTE 'CREATE INDEX IF NOT EXISTS idx_onboarding_product_modules_domain ON onboarding.product_modules(domain);';
      EXECUTE 'CREATE INDEX IF NOT EXISTS idx_onboarding_product_modules_active ON onboarding.product_modules(is_active) WHERE is_active = true;';

      EXECUTE $SEED$
        INSERT INTO onboarding.product_modules
          (id, name, name_ko, domain, freddy_ai_enabled, capabilities, rag_product_keys, icon, color_primary, description, description_ko, display_order, is_active)
        VALUES
          ('freshservice', 'Freshservice', '프레시서비스', 'itsm', true, '[]'::jsonb, ARRAY['freshservice','fs'], 'cog', 'blue', 'IT Service Management', 'IT 서비스 관리', 10, true),
          ('freshdesk', 'Freshdesk', '프레시데스크', 'customer_service', true, '[]'::jsonb, ARRAY['freshdesk','fd'], 'headset', 'green', 'Customer Support', '고객 지원', 20, true),
          ('freshchat', 'Freshchat', '프레시챗', 'customer_service', true, '[]'::jsonb, ARRAY['freshchat','fc'], 'comments', 'orange', 'Messaging & Chat', '메시징 및 채팅', 30, true),
          ('freshsales', 'Freshsales', '프레시세일즈', 'sales_marketing', true, '[]'::jsonb, ARRAY['freshsales','fsl'], 'chart-line', 'purple', 'CRM & Sales', 'CRM 및 영업', 40, true)
        ON CONFLICT (id) DO NOTHING;
      $SEED$;
    END IF;
  END IF;
END $$;

-- 2) onboarding.product_bundles
DO $$
BEGIN
  IF to_regclass('onboarding.product_bundles') IS NULL THEN
    IF to_regclass('public.product_bundles') IS NOT NULL THEN
      EXECUTE 'CREATE VIEW onboarding.product_bundles AS SELECT * FROM public.product_bundles;';
    ELSE
      EXECUTE $DDL$
        CREATE TABLE IF NOT EXISTS onboarding.product_bundles (
          id VARCHAR(50) PRIMARY KEY,
          name VARCHAR(100) NOT NULL,
          name_ko VARCHAR(100) NOT NULL,
          base_module_ids TEXT[] NOT NULL,
          integration_type VARCHAR(30) NOT NULL,
          workspace_type VARCHAR(20) NOT NULL,
          rag_product_keys TEXT[] NOT NULL DEFAULT '{}',
          integration_features JSONB,
          pricing_advantage_percent DECIMAL(5,2) DEFAULT 0,
          description TEXT,
          description_ko TEXT,
          display_order INT DEFAULT 0,
          is_active BOOLEAN DEFAULT true,
          created_at TIMESTAMPTZ DEFAULT NOW(),
          updated_at TIMESTAMPTZ DEFAULT NOW()
        );
      $DDL$;

      EXECUTE 'CREATE INDEX IF NOT EXISTS idx_onboarding_product_bundles_active ON onboarding.product_bundles(is_active) WHERE is_active = true;';

      EXECUTE $SEED$
        INSERT INTO onboarding.product_bundles
          (id, name, name_ko, base_module_ids, integration_type, workspace_type, rag_product_keys, description, description_ko, display_order, is_active)
        VALUES
          ('freshdesk_omni', 'Freshdesk Omni', '프레시데스크 옴니', ARRAY['freshdesk','freshchat'], 'native_unified', 'unified', ARRAY['freshdesk_omni','omni'], 'Unified Customer Experience', '통합 고객 경험', 15, true)
        ON CONFLICT (id) DO NOTHING;
      $SEED$;
    END IF;
  END IF;
END $$;

-- 기본 권한 (필요 시 프론트/타 서비스에서 직접 조회 가능)
GRANT USAGE ON SCHEMA onboarding TO anon, authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA onboarding TO anon, authenticated;
