-- ============================================
-- Migration: Copy Data to New Naming Tables
-- Date: 2025-11-27
-- Description: 기존 테이블 → 신규 네이밍 테이블 데이터 복사
-- Prerequisites: 20251127000001_create_new_naming_tables.sql 실행 완료
-- ============================================

-- ============================================
-- Phase 1: 독립 테이블 데이터 복사
-- ============================================

-- --------------------------------------------
-- 1.1 categories → kb_categories
-- --------------------------------------------
INSERT INTO kb_categories (
  id, name_ko, name_en, slug, description, icon, 
  display_order, is_active, product, created_at, updated_at
)
SELECT 
  id, name_ko, name_en, slug, description, icon,
  display_order, is_active, product, created_at, updated_at
FROM categories
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 1.2 products → product_catalog
-- --------------------------------------------
INSERT INTO product_catalog (
  id, product_id, name_ko, name_en, subtitle_ko, subtitle_en,
  category, category_ko, vendor, logo_url, hero_image_url,
  description_ko, description_en, basic_info, key_features,
  advanced_info, success_metrics, integrations,
  meta_title_ko, meta_title_en, meta_description_ko, meta_description_en,
  meta_keywords, slug, description_embedding, features_embedding,
  combined_embedding, embedding_model, embeddings_generated_at,
  is_active, is_featured, display_order, created_at, updated_at
)
SELECT 
  id, product_id, name_ko, name_en, subtitle_ko, subtitle_en,
  category, category_ko, vendor, logo_url, hero_image_url,
  description_ko, description_en, basic_info, key_features,
  advanced_info, success_metrics, integrations,
  meta_title_ko, meta_title_en, meta_description_ko, meta_description_en,
  meta_keywords, slug, description_embedding, features_embedding,
  combined_embedding, embedding_model, embeddings_generated_at,
  is_active, is_featured, display_order, created_at, updated_at
FROM products
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 1.3 services → product_services
-- --------------------------------------------
INSERT INTO product_services (
  id, service_type, name_ko, name_en, slug, badge,
  hero, cards_section, cards, process_steps, roadmap, cta,
  base_price_krw, pricing_model, pricing_details,
  is_active, display_order, created_at, updated_at
)
SELECT 
  id, service_type, name_ko, name_en, slug, badge,
  hero, cards_section, cards, process_steps, roadmap, cta,
  base_price_krw, pricing_model, pricing_details,
  is_active, display_order, created_at, updated_at
FROM services
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 1.4 search_queries → agent_search_cache
-- --------------------------------------------
INSERT INTO agent_search_cache (
  id, query_text, query_hash, query_embedding,
  ai_answer, ai_model, sources, product_filter, language,
  hit_count, last_used_at, expires_at, created_at
)
SELECT 
  id, query_text, query_hash, query_embedding,
  ai_answer, ai_model, sources, product_filter, language,
  COALESCE(hit_count, 0), COALESCE(last_used_at, now()), expires_at, created_at
FROM search_queries
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 1.5 agent_context_cache → agent_response_cache
-- --------------------------------------------
INSERT INTO agent_response_cache (
  id, query_hash, query_text, query_type,
  response_text, response_model, response_tokens,
  source_products, source_documents, source_services, source_pricing_plans,
  hit_count, last_used_at, expires_at, created_at
)
SELECT 
  id, query_hash, query_text, query_type,
  response_text, response_model, response_tokens,
  source_products, source_documents, source_services, source_pricing_plans,
  hit_count, last_used_at, expires_at, created_at
FROM agent_context_cache
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 1.6 tenants → tenant_orgs
-- --------------------------------------------
INSERT INTO tenant_orgs (
  id, slug, name, plan, use_shared_stores,
  gemini_ticket_store, gemini_article_store,
  created_at, updated_at, deleted_at
)
SELECT 
  id, slug, name, plan, use_shared_stores,
  gemini_ticket_store, gemini_article_store,
  created_at, updated_at, deleted_at
FROM tenants
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Phase 2: 1차 의존 테이블 데이터 복사
-- ============================================

-- --------------------------------------------
-- 2.1 folders → kb_folders
-- 주의: category_id는 kb_categories의 id로 매핑
-- --------------------------------------------
INSERT INTO kb_folders (
  id, category_id, name_ko, name_en, slug, description,
  icon, display_order, is_active, product, created_at, updated_at
)
SELECT 
  f.id, 
  f.category_id,  -- 동일한 UUID 사용 (kb_categories에 이미 복사됨)
  f.name_ko, f.name_en, f.slug, f.description,
  f.icon, f.display_order, f.is_active, f.product, f.created_at, f.updated_at
FROM folders f
WHERE EXISTS (SELECT 1 FROM kb_categories kc WHERE kc.id = f.category_id)
   OR f.category_id IS NULL
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 2.2 documents → kb_documents
-- --------------------------------------------
INSERT INTO kb_documents (
  id, csv_id, category_id, folder_id, product,
  title_ko, title_en, content_html_ko, content_html_en,
  content_text_ko, content_text_en, original_url, short_slug,
  seo_title_ko, seo_title_en, seo_description_ko, seo_description_en, seo_keywords,
  view_count, helpful_count, not_helpful_count,
  embedding, title_embedding, content_embedding, combined_embedding,
  embedding_model, embeddings_generated_at,
  published, is_featured, display_order, created_at, updated_at
)
SELECT 
  d.id, d.csv_id, d.category_id, d.folder_id, d.product,
  d.title_ko, d.title_en, d.content_html_ko, d.content_html_en,
  d.content_text_ko, d.content_text_en, d.original_url, d.short_slug,
  d.seo_title_ko, d.seo_title_en, d.seo_description_ko, d.seo_description_en, d.seo_keywords,
  COALESCE(d.view_count, 0), COALESCE(d.helpful_count, 0), COALESCE(d.not_helpful_count, 0),
  d.embedding, d.title_embedding, d.content_embedding, d.combined_embedding,
  d.embedding_model, d.embeddings_generated_at,
  d.published, COALESCE(d.is_featured, false), COALESCE(d.display_order, 0), d.created_at, d.updated_at
FROM documents d
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 2.3 pricing_plans → product_pricing_plans
-- --------------------------------------------
INSERT INTO product_pricing_plans (
  id, product_id, plan_id, plan_name, plan_name_ko,
  monthly_price_usd, yearly_price_usd, custom_pricing,
  session_pricing, max_users, max_agents, max_storage_gb,
  features, features_en, is_recommended, is_popular,
  is_enterprise_only, display_order, created_at, updated_at
)
SELECT 
  pp.id,
  pp.product_id,  -- product_catalog에 이미 복사됨
  pp.plan_id, pp.plan_name, pp.plan_name_ko,
  pp.monthly_price_usd, pp.yearly_price_usd, pp.custom_pricing,
  pp.session_pricing, pp.max_users, pp.max_agents, pp.max_storage_gb,
  pp.features, pp.features_en, pp.is_recommended, pp.is_popular,
  pp.is_enterprise_only, pp.display_order, pp.created_at, pp.updated_at
FROM pricing_plans pp
WHERE EXISTS (SELECT 1 FROM product_catalog pc WHERE pc.id = pp.product_id)
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 2.4 ticket_metadata → tenant_ticket_metadata
-- --------------------------------------------
INSERT INTO tenant_ticket_metadata (
  id, tenant_id, platform, ticket_id, external_id,
  status, priority, source, requester, requester_id,
  responder, responder_id, group_name, group_id, tags,
  ticket_created_at, ticket_updated_at, synced_at
)
SELECT 
  tm.id,
  tm.tenant_id,  -- tenant_orgs에 이미 복사됨
  tm.platform, tm.ticket_id, tm.external_id,
  tm.status, tm.priority, tm.source, tm.requester, tm.requester_id,
  tm.responder, tm.responder_id, tm.group_name, tm.group_id, tm.tags,
  tm.ticket_created_at, tm.ticket_updated_at, tm.synced_at
FROM ticket_metadata tm
WHERE EXISTS (SELECT 1 FROM tenant_orgs t WHERE t.id = tm.tenant_id)
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 2.5 article_metadata → tenant_article_metadata
-- --------------------------------------------
INSERT INTO tenant_article_metadata (
  id, tenant_id, platform, article_id, external_id,
  title, folder_id, folder_name, category_id, category_name, status,
  article_created_at, article_updated_at, synced_at
)
SELECT 
  am.id,
  am.tenant_id,  -- tenant_orgs에 이미 복사됨
  am.platform, am.article_id, am.external_id,
  am.title, am.folder_id, am.folder_name, am.category_id, am.category_name, am.status,
  am.article_created_at, am.article_updated_at, am.synced_at
FROM article_metadata am
WHERE EXISTS (SELECT 1 FROM tenant_orgs t WHERE t.id = am.tenant_id)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Phase 3: 2차 의존 테이블 데이터 복사
-- ============================================

-- --------------------------------------------
-- 3.1 document_feedback → kb_feedback
-- --------------------------------------------
INSERT INTO kb_feedback (
  id, document_id, is_helpful, feedback_text, feedback_category,
  user_session_id, user_agent, ip_hash, created_at
)
SELECT 
  df.id,
  df.document_id,  -- kb_documents에 이미 복사됨
  df.is_helpful, df.feedback_text, df.feedback_category,
  df.user_session_id, df.user_agent, df.ip_hash, df.created_at
FROM document_feedback df
WHERE EXISTS (SELECT 1 FROM kb_documents kd WHERE kd.id = df.document_id)
ON CONFLICT (id) DO NOTHING;

-- --------------------------------------------
-- 3.2 product_documents → kb_product_documents
-- --------------------------------------------
INSERT INTO kb_product_documents (
  id, product_id, document_id, relationship_type, display_order, created_at
)
SELECT 
  pd.id,
  pd.product_id,   -- product_catalog에 이미 복사됨
  pd.document_id,  -- kb_documents에 이미 복사됨
  pd.relationship_type, pd.display_order, pd.created_at
FROM product_documents pd
WHERE EXISTS (SELECT 1 FROM product_catalog pc WHERE pc.id = pd.product_id)
  AND EXISTS (SELECT 1 FROM kb_documents kd WHERE kd.id = pd.document_id)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- End of Migration: Copy Data
-- ============================================
