-- ============================================
-- Migration: Create New Naming Convention Tables
-- Date: 2025-11-27
-- Description: 신규 네이밍 규칙 테이블 생성 (데이터 복사 전 단계)
-- Naming Convention: {domain}_{entity}
--   - kb_* : 지식베이스 (Knowledge Base)
--   - product_* : 제품/가격
--   - agent_* : AI/에이전트
--   - tenant_* : 고객사 (Tenant)
--   - blog_* : 블로그 (기존 유지)
--   - onboarding_* : 온보딩 (향후 추가)
-- ============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- Phase 1: 독립 테이블 (FK 의존성 없음)
-- ============================================

-- --------------------------------------------
-- 1.1 kb_categories (← categories)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS kb_categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name_ko text NOT NULL,
  name_en text,
  slug text UNIQUE NOT NULL,
  description text,
  icon text,
  display_order int DEFAULT 0,
  is_active boolean DEFAULT true,
  product text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_kb_categories_slug ON kb_categories(slug);
CREATE INDEX idx_kb_categories_product ON kb_categories(product);
CREATE INDEX idx_kb_categories_active ON kb_categories(is_active) WHERE is_active = true;

COMMENT ON TABLE kb_categories IS 'Knowledge Base categories (migrated from categories)';

-- --------------------------------------------
-- 1.2 product_catalog (← products)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS product_catalog (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- 기본 식별자
  product_id text UNIQUE NOT NULL,
  
  -- 기본 정보
  name_ko text NOT NULL,
  name_en text,
  subtitle_ko text,
  subtitle_en text,
  
  -- 분류
  category text NOT NULL,
  category_ko text,
  vendor text NOT NULL,
  
  -- 로고/이미지
  logo_url text,
  hero_image_url text,
  
  -- 상세 설명
  description_ko text,
  description_en text,
  
  -- JSONB 필드들
  basic_info jsonb,
  key_features jsonb,
  advanced_info jsonb,
  success_metrics jsonb,
  integrations jsonb,
  
  -- SEO
  meta_title_ko text,
  meta_title_en text,
  meta_description_ko text,
  meta_description_en text,
  meta_keywords text[],
  slug text UNIQUE NOT NULL,
  
  -- 벡터 임베딩 (1536 dimensions)
  description_embedding vector(1536),
  features_embedding vector(1536),
  combined_embedding vector(1536),
  
  embedding_model text DEFAULT 'text-embedding-3-small',
  embeddings_generated_at timestamptz,
  
  -- 메타데이터
  is_active boolean DEFAULT true,
  is_featured boolean DEFAULT false,
  display_order int DEFAULT 0,
  
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_product_catalog_category ON product_catalog(category);
CREATE INDEX idx_product_catalog_vendor ON product_catalog(vendor);
CREATE INDEX idx_product_catalog_active ON product_catalog(is_active) WHERE is_active = true;
CREATE INDEX idx_product_catalog_featured ON product_catalog(is_featured) WHERE is_featured = true;
CREATE INDEX idx_product_catalog_slug ON product_catalog(slug);

-- 벡터 검색 인덱스 (HNSW)
CREATE INDEX idx_product_catalog_combined_embedding
  ON product_catalog
  USING hnsw (combined_embedding vector_cosine_ops);

CREATE INDEX idx_product_catalog_features_embedding
  ON product_catalog
  USING hnsw (features_embedding vector_cosine_ops);

-- 전문 검색 인덱스
CREATE INDEX idx_product_catalog_fts_ko
  ON product_catalog
  USING GIN (to_tsvector('simple', coalesce(name_ko, '') || ' ' || coalesce(description_ko, '')));

COMMENT ON TABLE product_catalog IS 'Product catalog with vector search (migrated from products)';

-- --------------------------------------------
-- 1.3 product_services (← services)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS product_services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  service_type text NOT NULL,
  name_ko text NOT NULL,
  name_en text,
  slug text UNIQUE NOT NULL,
  badge text,
  
  hero jsonb,
  cards_section jsonb,
  cards jsonb,
  process_steps jsonb,
  roadmap jsonb,
  cta jsonb,
  
  base_price_krw decimal(12,2),
  pricing_model text,
  pricing_details jsonb,
  
  is_active boolean DEFAULT true,
  display_order int DEFAULT 0,
  
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_product_services_type ON product_services(service_type);
CREATE INDEX idx_product_services_active ON product_services(is_active) WHERE is_active = true;

COMMENT ON TABLE product_services IS 'Professional services catalog (migrated from services)';

-- --------------------------------------------
-- 1.4 agent_search_cache (← search_queries)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS agent_search_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  query_text text NOT NULL,
  query_hash text UNIQUE,
  query_embedding vector(1536),
  
  ai_answer text,
  ai_model text,
  sources jsonb,
  
  product_filter text,
  language text DEFAULT 'ko',
  
  hit_count int DEFAULT 0,
  last_used_at timestamptz DEFAULT now(),
  expires_at timestamptz,
  
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_agent_search_cache_hash ON agent_search_cache(query_hash);
CREATE INDEX idx_agent_search_cache_product ON agent_search_cache(product_filter);
CREATE INDEX idx_agent_search_cache_expires ON agent_search_cache(expires_at);
CREATE INDEX idx_agent_search_cache_hits ON agent_search_cache(hit_count DESC);

COMMENT ON TABLE agent_search_cache IS 'AI search query cache (migrated from search_queries)';

-- --------------------------------------------
-- 1.5 agent_response_cache (← agent_context_cache)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS agent_response_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  query_hash text UNIQUE NOT NULL,
  query_text text NOT NULL,
  query_type text NOT NULL,
  
  response_text text NOT NULL,
  response_model text,
  response_tokens int,
  
  source_products uuid[],
  source_documents uuid[],
  source_services uuid[],
  source_pricing_plans uuid[],
  
  hit_count int DEFAULT 0,
  last_used_at timestamptz DEFAULT now(),
  expires_at timestamptz,
  
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_agent_response_cache_hash ON agent_response_cache(query_hash);
CREATE INDEX idx_agent_response_cache_type ON agent_response_cache(query_type);
CREATE INDEX idx_agent_response_cache_expires ON agent_response_cache(expires_at);
CREATE INDEX idx_agent_response_cache_hits ON agent_response_cache(hit_count DESC);

COMMENT ON TABLE agent_response_cache IS 'AI agent response cache (migrated from agent_context_cache)';

-- --------------------------------------------
-- 1.6 tenant_orgs (← tenants)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_orgs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  plan VARCHAR(20) DEFAULT 'basic' CHECK (plan IN ('basic', 'pro', 'enterprise')),
  
  use_shared_stores BOOLEAN DEFAULT TRUE,
  gemini_ticket_store VARCHAR(255),
  gemini_article_store VARCHAR(255),
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_tenant_orgs_slug ON tenant_orgs(slug) WHERE deleted_at IS NULL;

COMMENT ON TABLE tenant_orgs IS 'Tenant organizations (migrated from tenants)';

-- ============================================
-- Phase 2: 1차 의존 테이블
-- ============================================

-- --------------------------------------------
-- 2.1 kb_folders (← folders, FK: kb_categories)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS kb_folders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id uuid REFERENCES kb_categories(id) ON DELETE CASCADE,
  name_ko text NOT NULL,
  name_en text,
  slug text NOT NULL,
  description text,
  icon text,
  display_order int DEFAULT 0,
  is_active boolean DEFAULT true,
  product text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  
  UNIQUE(category_id, slug)
);

CREATE INDEX idx_kb_folders_category ON kb_folders(category_id);
CREATE INDEX idx_kb_folders_slug ON kb_folders(slug);
CREATE INDEX idx_kb_folders_product ON kb_folders(product);

COMMENT ON TABLE kb_folders IS 'Knowledge Base folders (migrated from folders)';

-- --------------------------------------------
-- 2.2 kb_documents (← documents, FK: kb_categories, kb_folders)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS kb_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- 원본 식별자
  csv_id bigint UNIQUE,
  
  -- 분류
  category_id uuid REFERENCES kb_categories(id) ON DELETE SET NULL,
  folder_id uuid REFERENCES kb_folders(id) ON DELETE SET NULL,
  product text,
  
  -- 콘텐츠
  title_ko text NOT NULL,
  title_en text,
  content_html_ko text,
  content_html_en text,
  content_text_ko text,
  content_text_en text,
  
  -- URL/슬러그
  original_url text,
  short_slug text UNIQUE,
  
  -- 메타데이터
  seo_title_ko text,
  seo_title_en text,
  seo_description_ko text,
  seo_description_en text,
  seo_keywords text[],
  
  -- 통계
  view_count int DEFAULT 0,
  helpful_count int DEFAULT 0,
  not_helpful_count int DEFAULT 0,
  
  -- 벡터 임베딩
  embedding vector(1536),
  title_embedding vector(1536),
  content_embedding vector(1536),
  combined_embedding vector(1536),
  
  embedding_model text DEFAULT 'text-embedding-3-small',
  embeddings_generated_at timestamptz,
  
  -- 상태
  published boolean DEFAULT true,
  is_featured boolean DEFAULT false,
  display_order int DEFAULT 0,
  
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_kb_documents_category ON kb_documents(category_id);
CREATE INDEX idx_kb_documents_folder ON kb_documents(folder_id);
CREATE INDEX idx_kb_documents_product ON kb_documents(product);
CREATE INDEX idx_kb_documents_published ON kb_documents(published) WHERE published = true;
CREATE INDEX idx_kb_documents_slug ON kb_documents(short_slug);

-- 벡터 검색 인덱스 (HNSW)
CREATE INDEX idx_kb_documents_embedding
  ON kb_documents
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_kb_documents_combined_embedding
  ON kb_documents
  USING hnsw (combined_embedding vector_cosine_ops);

-- 전문 검색 인덱스
CREATE INDEX idx_kb_documents_fts_ko
  ON kb_documents
  USING GIN (to_tsvector('simple', coalesce(title_ko, '') || ' ' || coalesce(content_text_ko, '')));

COMMENT ON TABLE kb_documents IS 'Knowledge Base documents with vector search (migrated from documents)';

-- --------------------------------------------
-- 2.3 product_pricing_plans (← pricing_plans, FK: product_catalog)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS product_pricing_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid REFERENCES product_catalog(id) ON DELETE CASCADE,
  
  plan_id text NOT NULL,
  plan_name text NOT NULL,
  plan_name_ko text,
  
  monthly_price_usd decimal(10,2),
  yearly_price_usd decimal(10,2),
  custom_pricing boolean DEFAULT false,
  
  session_pricing jsonb,
  
  max_users int,
  max_agents int,
  max_storage_gb int,
  
  features jsonb NOT NULL,
  features_en jsonb,
  
  is_recommended boolean DEFAULT false,
  is_popular boolean DEFAULT false,
  is_enterprise_only boolean DEFAULT false,
  display_order int DEFAULT 0,
  
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  
  UNIQUE(product_id, plan_id)
);

CREATE INDEX idx_product_pricing_plans_product ON product_pricing_plans(product_id);
CREATE INDEX idx_product_pricing_plans_monthly ON product_pricing_plans(monthly_price_usd) WHERE monthly_price_usd IS NOT NULL;
CREATE INDEX idx_product_pricing_plans_recommended ON product_pricing_plans(is_recommended) WHERE is_recommended = true;

COMMENT ON TABLE product_pricing_plans IS 'Product pricing plans (migrated from pricing_plans)';

-- --------------------------------------------
-- 2.4 tenant_ticket_metadata (← ticket_metadata, FK: tenant_orgs)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_ticket_metadata (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenant_orgs(id) ON DELETE CASCADE,
  platform VARCHAR(50) NOT NULL,
  
  ticket_id BIGINT NOT NULL,
  external_id VARCHAR(100),
  
  status VARCHAR(50),
  priority VARCHAR(20),
  source VARCHAR(50),
  requester VARCHAR(255),
  requester_id BIGINT,
  responder VARCHAR(255),
  responder_id BIGINT,
  group_name VARCHAR(255),
  group_id BIGINT,
  tags TEXT[],
  
  ticket_created_at TIMESTAMPTZ NOT NULL,
  ticket_updated_at TIMESTAMPTZ NOT NULL,
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, platform, ticket_id)
);

CREATE INDEX idx_tenant_ticket_meta_tenant_date ON tenant_ticket_metadata(tenant_id, ticket_created_at DESC);
CREATE INDEX idx_tenant_ticket_meta_tenant_updated ON tenant_ticket_metadata(tenant_id, ticket_updated_at DESC);
CREATE INDEX idx_tenant_ticket_meta_requester ON tenant_ticket_metadata(tenant_id, requester);
CREATE INDEX idx_tenant_ticket_meta_status ON tenant_ticket_metadata(tenant_id, status);

COMMENT ON TABLE tenant_ticket_metadata IS 'Tenant ticket metadata for filtering (migrated from ticket_metadata)';

-- --------------------------------------------
-- 2.5 tenant_article_metadata (← article_metadata, FK: tenant_orgs)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_article_metadata (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenant_orgs(id) ON DELETE CASCADE,
  platform VARCHAR(50) NOT NULL,
  
  article_id BIGINT NOT NULL,
  external_id VARCHAR(100),
  
  title VARCHAR(500),
  folder_id BIGINT,
  folder_name VARCHAR(255),
  category_id BIGINT,
  category_name VARCHAR(255),
  status VARCHAR(50),
  
  article_created_at TIMESTAMPTZ NOT NULL,
  article_updated_at TIMESTAMPTZ NOT NULL,
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, platform, article_id)
);

CREATE INDEX idx_tenant_article_meta_tenant_date ON tenant_article_metadata(tenant_id, article_created_at DESC);
CREATE INDEX idx_tenant_article_meta_folder ON tenant_article_metadata(tenant_id, folder_id);
CREATE INDEX idx_tenant_article_meta_category ON tenant_article_metadata(tenant_id, category_id);

COMMENT ON TABLE tenant_article_metadata IS 'Tenant article metadata (migrated from article_metadata)';

-- ============================================
-- Phase 3: 2차 의존 테이블
-- ============================================

-- --------------------------------------------
-- 3.1 kb_feedback (← document_feedback, FK: kb_documents)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS kb_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid REFERENCES kb_documents(id) ON DELETE CASCADE,
  
  is_helpful boolean NOT NULL,
  feedback_text text,
  feedback_category text,
  
  user_session_id text,
  user_agent text,
  ip_hash text,
  
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_kb_feedback_document ON kb_feedback(document_id);
CREATE INDEX idx_kb_feedback_helpful ON kb_feedback(is_helpful);
CREATE INDEX idx_kb_feedback_created ON kb_feedback(created_at DESC);

COMMENT ON TABLE kb_feedback IS 'Document feedback (migrated from document_feedback)';

-- --------------------------------------------
-- 3.2 kb_product_documents (← product_documents, FK: product_catalog, kb_documents)
-- --------------------------------------------
CREATE TABLE IF NOT EXISTS kb_product_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid REFERENCES product_catalog(id) ON DELETE CASCADE,
  document_id uuid REFERENCES kb_documents(id) ON DELETE CASCADE,
  
  relationship_type text,
  display_order int DEFAULT 0,
  
  created_at timestamptz DEFAULT now(),
  
  UNIQUE(product_id, document_id)
);

CREATE INDEX idx_kb_product_docs_product ON kb_product_documents(product_id);
CREATE INDEX idx_kb_product_docs_document ON kb_product_documents(document_id);
CREATE INDEX idx_kb_product_docs_type ON kb_product_documents(relationship_type);

COMMENT ON TABLE kb_product_documents IS 'Product-Document relationship (migrated from product_documents)';

-- ============================================
-- Phase 4: 함수 생성
-- ============================================

-- Semantic Document Search (for kb_documents)
CREATE OR REPLACE FUNCTION search_kb_documents(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 5,
  product_filter text DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  csv_id bigint,
  title_ko text,
  title_en text,
  content_text_ko text,
  short_slug text,
  product text,
  category_name text,
  folder_name text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.csv_id,
    d.title_ko,
    d.title_en,
    substring(d.content_text_ko, 1, 500) as content_text_ko,
    d.short_slug,
    d.product,
    c.name_ko as category_name,
    f.name_ko as folder_name,
    1 - (d.embedding <=> query_embedding) as similarity
  FROM kb_documents d
  LEFT JOIN kb_categories c ON d.category_id = c.id
  LEFT JOIN kb_folders f ON d.folder_id = f.id
  WHERE
    d.published = true
    AND d.embedding IS NOT NULL
    AND 1 - (d.embedding <=> query_embedding) > match_threshold
    AND (product_filter IS NULL OR d.product = product_filter)
  ORDER BY d.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_kb_documents IS 'Semantic search for KB documents';

-- Semantic Product Search (for product_catalog)
CREATE OR REPLACE FUNCTION search_product_catalog(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 10,
  filter_category text DEFAULT NULL,
  filter_vendor text DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  product_id text,
  name_ko text,
  description_ko text,
  category text,
  vendor text,
  slug text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    p.id,
    p.product_id,
    p.name_ko,
    p.description_ko,
    p.category,
    p.vendor,
    p.slug,
    1 - (p.combined_embedding <=> query_embedding) as similarity
  FROM product_catalog p
  WHERE
    p.is_active = true
    AND (filter_category IS NULL OR p.category = filter_category)
    AND (filter_vendor IS NULL OR p.vendor = filter_vendor)
    AND 1 - (p.combined_embedding <=> query_embedding) > match_threshold
  ORDER BY p.combined_embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_product_catalog IS 'Semantic search for product catalog';

-- Get Product with Pricing
CREATE OR REPLACE FUNCTION get_product_with_pricing_v2(
  p_slug text
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  result jsonb;
BEGIN
  SELECT jsonb_build_object(
    'product', row_to_json(p.*),
    'pricing_plans', (
      SELECT jsonb_agg(row_to_json(pp.*) ORDER BY pp.display_order, pp.monthly_price_usd)
      FROM product_pricing_plans pp
      WHERE pp.product_id = p.id
    )
  ) INTO result
  FROM product_catalog p
  WHERE p.slug = p_slug AND p.is_active = true;
  
  RETURN result;
END;
$$;

COMMENT ON FUNCTION get_product_with_pricing_v2 IS 'Get product with all pricing plans (v2 for new tables)';

-- Get ticket IDs by date range (for tenant_ticket_metadata)
CREATE OR REPLACE FUNCTION get_tenant_ticket_ids_by_date(
  p_tenant_id UUID,
  p_platform VARCHAR,
  p_start_date TIMESTAMPTZ DEFAULT NULL,
  p_end_date TIMESTAMPTZ DEFAULT NULL,
  p_limit INT DEFAULT 1000
)
RETURNS TABLE(ticket_id BIGINT) AS $$
BEGIN
  RETURN QUERY
  SELECT tm.ticket_id
  FROM tenant_ticket_metadata tm
  WHERE tm.tenant_id = p_tenant_id
    AND (p_platform IS NULL OR tm.platform = p_platform)
    AND (p_start_date IS NULL OR tm.ticket_created_at >= p_start_date)
    AND (p_end_date IS NULL OR tm.ticket_created_at <= p_end_date)
  ORDER BY tm.ticket_created_at DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_tenant_ticket_ids_by_date IS 'Get ticket IDs by date range for tenant';

-- ============================================
-- End of Migration: Create New Naming Tables
-- ============================================
