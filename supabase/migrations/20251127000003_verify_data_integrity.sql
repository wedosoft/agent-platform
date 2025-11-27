-- ============================================
-- Migration: Verify Data Integrity
-- Date: 2025-11-27
-- Description: 데이터 무결성 검증 (row count, FK, 벡터 인덱스)
-- Run this AFTER 20251127000002_copy_data_to_new_tables.sql
-- ============================================

-- ============================================
-- 1. Row Count 비교
-- ============================================

SELECT '=== Row Count Comparison ===' AS section;

SELECT 
  'categories → kb_categories' AS migration,
  (SELECT COUNT(*) FROM categories) AS old_count,
  (SELECT COUNT(*) FROM kb_categories) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM categories) = (SELECT COUNT(*) FROM kb_categories) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'products → product_catalog' AS migration,
  (SELECT COUNT(*) FROM products) AS old_count,
  (SELECT COUNT(*) FROM product_catalog) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM products) = (SELECT COUNT(*) FROM product_catalog) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'services → product_services' AS migration,
  (SELECT COUNT(*) FROM services) AS old_count,
  (SELECT COUNT(*) FROM product_services) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM services) = (SELECT COUNT(*) FROM product_services) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'folders → kb_folders' AS migration,
  (SELECT COUNT(*) FROM folders) AS old_count,
  (SELECT COUNT(*) FROM kb_folders) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM folders) = (SELECT COUNT(*) FROM kb_folders) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'documents → kb_documents' AS migration,
  (SELECT COUNT(*) FROM documents) AS old_count,
  (SELECT COUNT(*) FROM kb_documents) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM documents) = (SELECT COUNT(*) FROM kb_documents) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'pricing_plans → product_pricing_plans' AS migration,
  (SELECT COUNT(*) FROM pricing_plans) AS old_count,
  (SELECT COUNT(*) FROM product_pricing_plans) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM pricing_plans) = (SELECT COUNT(*) FROM product_pricing_plans) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'tenants → tenant_orgs' AS migration,
  (SELECT COUNT(*) FROM tenants) AS old_count,
  (SELECT COUNT(*) FROM tenant_orgs) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM tenants) = (SELECT COUNT(*) FROM tenant_orgs) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'ticket_metadata → tenant_ticket_metadata' AS migration,
  (SELECT COUNT(*) FROM ticket_metadata) AS old_count,
  (SELECT COUNT(*) FROM tenant_ticket_metadata) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM ticket_metadata) = (SELECT COUNT(*) FROM tenant_ticket_metadata) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

SELECT 
  'article_metadata → tenant_article_metadata' AS migration,
  (SELECT COUNT(*) FROM article_metadata) AS old_count,
  (SELECT COUNT(*) FROM tenant_article_metadata) AS new_count,
  CASE 
    WHEN (SELECT COUNT(*) FROM article_metadata) = (SELECT COUNT(*) FROM tenant_article_metadata) 
    THEN '✅ MATCH' 
    ELSE '❌ MISMATCH' 
  END AS status;

-- Optional tables (may not exist)
SELECT 
  'search_queries → agent_search_cache' AS migration,
  COALESCE((SELECT COUNT(*) FROM search_queries), 0) AS old_count,
  (SELECT COUNT(*) FROM agent_search_cache) AS new_count,
  '⚠️ CHECK MANUALLY' AS status;

SELECT 
  'agent_context_cache → agent_response_cache' AS migration,
  COALESCE((SELECT COUNT(*) FROM agent_context_cache), 0) AS old_count,
  (SELECT COUNT(*) FROM agent_response_cache) AS new_count,
  '⚠️ CHECK MANUALLY' AS status;

SELECT 
  'document_feedback → kb_feedback' AS migration,
  COALESCE((SELECT COUNT(*) FROM document_feedback), 0) AS old_count,
  (SELECT COUNT(*) FROM kb_feedback) AS new_count,
  '⚠️ CHECK MANUALLY' AS status;

SELECT 
  'product_documents → kb_product_documents' AS migration,
  COALESCE((SELECT COUNT(*) FROM product_documents), 0) AS old_count,
  (SELECT COUNT(*) FROM kb_product_documents) AS new_count,
  '⚠️ CHECK MANUALLY' AS status;

-- ============================================
-- 2. Foreign Key 무결성 검증
-- ============================================

SELECT '=== Foreign Key Integrity ===' AS section;

-- kb_folders → kb_categories
SELECT 
  'kb_folders.category_id → kb_categories' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM kb_folders f
LEFT JOIN kb_categories c ON f.category_id = c.id
WHERE f.category_id IS NOT NULL AND c.id IS NULL;

-- kb_documents → kb_categories
SELECT 
  'kb_documents.category_id → kb_categories' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM kb_documents d
LEFT JOIN kb_categories c ON d.category_id = c.id
WHERE d.category_id IS NOT NULL AND c.id IS NULL;

-- kb_documents → kb_folders
SELECT 
  'kb_documents.folder_id → kb_folders' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM kb_documents d
LEFT JOIN kb_folders f ON d.folder_id = f.id
WHERE d.folder_id IS NOT NULL AND f.id IS NULL;

-- product_pricing_plans → product_catalog
SELECT 
  'product_pricing_plans.product_id → product_catalog' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM product_pricing_plans pp
LEFT JOIN product_catalog p ON pp.product_id = p.id
WHERE p.id IS NULL;

-- tenant_ticket_metadata → tenant_orgs
SELECT 
  'tenant_ticket_metadata.tenant_id → tenant_orgs' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM tenant_ticket_metadata tm
LEFT JOIN tenant_orgs t ON tm.tenant_id = t.id
WHERE t.id IS NULL;

-- tenant_article_metadata → tenant_orgs
SELECT 
  'tenant_article_metadata.tenant_id → tenant_orgs' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM tenant_article_metadata am
LEFT JOIN tenant_orgs t ON am.tenant_id = t.id
WHERE t.id IS NULL;

-- kb_feedback → kb_documents
SELECT 
  'kb_feedback.document_id → kb_documents' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM kb_feedback fb
LEFT JOIN kb_documents d ON fb.document_id = d.id
WHERE d.id IS NULL;

-- kb_product_documents → product_catalog
SELECT 
  'kb_product_documents.product_id → product_catalog' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM kb_product_documents pd
LEFT JOIN product_catalog p ON pd.product_id = p.id
WHERE p.id IS NULL;

-- kb_product_documents → kb_documents
SELECT 
  'kb_product_documents.document_id → kb_documents' AS fk_check,
  COUNT(*) AS orphan_count,
  CASE WHEN COUNT(*) = 0 THEN '✅ OK' ELSE '❌ ORPHANS FOUND' END AS status
FROM kb_product_documents pd
LEFT JOIN kb_documents d ON pd.document_id = d.id
WHERE d.id IS NULL;

-- ============================================
-- 3. 벡터 인덱스 검증
-- ============================================

SELECT '=== Vector Index Verification ===' AS section;

-- kb_documents embedding count
SELECT 
  'kb_documents embeddings' AS check_item,
  COUNT(*) AS total_docs,
  COUNT(embedding) AS with_embedding,
  COUNT(combined_embedding) AS with_combined,
  ROUND(COUNT(embedding)::numeric / NULLIF(COUNT(*), 0) * 100, 1) || '%' AS coverage
FROM kb_documents;

-- product_catalog embedding count
SELECT 
  'product_catalog embeddings' AS check_item,
  COUNT(*) AS total_products,
  COUNT(combined_embedding) AS with_combined,
  COUNT(features_embedding) AS with_features,
  ROUND(COUNT(combined_embedding)::numeric / NULLIF(COUNT(*), 0) * 100, 1) || '%' AS coverage
FROM product_catalog;

-- ============================================
-- 4. 인덱스 상태 확인
-- ============================================

SELECT '=== Index Status ===' AS section;

SELECT 
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_indexes
WHERE tablename IN (
  'kb_categories', 'kb_folders', 'kb_documents', 'kb_feedback', 'kb_product_documents',
  'product_catalog', 'product_pricing_plans', 'product_services',
  'agent_search_cache', 'agent_response_cache',
  'tenant_orgs', 'tenant_ticket_metadata', 'tenant_article_metadata'
)
ORDER BY tablename, indexname;

-- ============================================
-- 5. 함수 검증 (간단한 호출 테스트)
-- ============================================

SELECT '=== Function Verification ===' AS section;

-- search_kb_documents 함수 존재 확인
SELECT 
  'search_kb_documents' AS function_name,
  CASE WHEN EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'search_kb_documents'
  ) THEN '✅ EXISTS' ELSE '❌ NOT FOUND' END AS status;

-- search_product_catalog 함수 존재 확인
SELECT 
  'search_product_catalog' AS function_name,
  CASE WHEN EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'search_product_catalog'
  ) THEN '✅ EXISTS' ELSE '❌ NOT FOUND' END AS status;

-- get_product_with_pricing_v2 함수 존재 확인
SELECT 
  'get_product_with_pricing_v2' AS function_name,
  CASE WHEN EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'get_product_with_pricing_v2'
  ) THEN '✅ EXISTS' ELSE '❌ NOT FOUND' END AS status;

-- get_tenant_ticket_ids_by_date 함수 존재 확인
SELECT 
  'get_tenant_ticket_ids_by_date' AS function_name,
  CASE WHEN EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'get_tenant_ticket_ids_by_date'
  ) THEN '✅ EXISTS' ELSE '❌ NOT FOUND' END AS status;

-- ============================================
-- 6. 요약 보고서
-- ============================================

SELECT '=== Migration Summary ===' AS section;

SELECT 
  'Total new tables created' AS metric,
  COUNT(*) AS value
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'kb_categories', 'kb_folders', 'kb_documents', 'kb_feedback', 'kb_product_documents',
    'product_catalog', 'product_pricing_plans', 'product_services',
    'agent_search_cache', 'agent_response_cache',
    'tenant_orgs', 'tenant_ticket_metadata', 'tenant_article_metadata'
  );

SELECT 
  'Total records in new tables' AS metric,
  (SELECT COUNT(*) FROM kb_categories) +
  (SELECT COUNT(*) FROM kb_folders) +
  (SELECT COUNT(*) FROM kb_documents) +
  (SELECT COUNT(*) FROM kb_feedback) +
  (SELECT COUNT(*) FROM kb_product_documents) +
  (SELECT COUNT(*) FROM product_catalog) +
  (SELECT COUNT(*) FROM product_pricing_plans) +
  (SELECT COUNT(*) FROM product_services) +
  (SELECT COUNT(*) FROM agent_search_cache) +
  (SELECT COUNT(*) FROM agent_response_cache) +
  (SELECT COUNT(*) FROM tenant_orgs) +
  (SELECT COUNT(*) FROM tenant_ticket_metadata) +
  (SELECT COUNT(*) FROM tenant_article_metadata) AS value;

-- ============================================
-- End of Verification
-- ============================================
