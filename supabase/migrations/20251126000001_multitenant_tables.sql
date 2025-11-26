-- Migration: Create multitenant tables
-- Date: 2025-11-26
-- Description: Tables for multitenant support with platform isolation

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Tenants Table
-- ============================================
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) UNIQUE NOT NULL,  -- e.g., 'wedosoft', 'acme'
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(20) DEFAULT 'basic' CHECK (plan IN ('basic', 'pro', 'enterprise')),
    
    -- Gemini Store configuration
    use_shared_stores BOOLEAN DEFAULT TRUE,
    gemini_ticket_store VARCHAR(255),   -- Custom store (NULL = use shared)
    gemini_article_store VARCHAR(255),  -- Custom store (NULL = use shared)
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ  -- Soft delete
);

CREATE INDEX idx_tenants_slug ON tenants(slug) WHERE deleted_at IS NULL;

-- ============================================
-- Tenant Platforms Table
-- ============================================
CREATE TABLE IF NOT EXISTS tenant_platforms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('freshdesk', 'zendesk', 'intercom', 'web', 'api')),
    
    -- Platform-specific configuration
    domain VARCHAR(255),  -- e.g., 'wedosoft.freshdesk.com'
    enabled BOOLEAN DEFAULT TRUE,
    api_key_hash VARCHAR(64),  -- SHA256 hash of API key (optional verification)
    custom_store VARCHAR(255),  -- Platform-specific store override
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, platform)
);

CREATE INDEX idx_tenant_platforms_tenant ON tenant_platforms(tenant_id);
CREATE INDEX idx_tenant_platforms_domain ON tenant_platforms(domain);

-- ============================================
-- Ticket Metadata Table (for date filtering)
-- ============================================
CREATE TABLE IF NOT EXISTS ticket_metadata (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    
    -- Ticket identifiers
    ticket_id BIGINT NOT NULL,
    external_id VARCHAR(100),  -- Original ID from the platform
    
    -- Filterable fields
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
    
    -- Timestamps (critical for date filtering)
    ticket_created_at TIMESTAMPTZ NOT NULL,
    ticket_updated_at TIMESTAMPTZ NOT NULL,
    
    -- Sync metadata
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, platform, ticket_id)
);

-- Indexes for common query patterns
CREATE INDEX idx_ticket_meta_tenant_date ON ticket_metadata(tenant_id, ticket_created_at DESC);
CREATE INDEX idx_ticket_meta_tenant_updated ON ticket_metadata(tenant_id, ticket_updated_at DESC);
CREATE INDEX idx_ticket_meta_requester ON ticket_metadata(tenant_id, requester);
CREATE INDEX idx_ticket_meta_status ON ticket_metadata(tenant_id, status);
CREATE INDEX idx_ticket_meta_priority ON ticket_metadata(tenant_id, priority);

-- ============================================
-- Article Metadata Table (for KB articles)
-- ============================================
CREATE TABLE IF NOT EXISTS article_metadata (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    
    -- Article identifiers
    article_id BIGINT NOT NULL,
    external_id VARCHAR(100),
    
    -- Filterable fields
    title VARCHAR(500),
    folder_id BIGINT,
    folder_name VARCHAR(255),
    category_id BIGINT,
    category_name VARCHAR(255),
    status VARCHAR(50),  -- draft, published
    
    -- Timestamps
    article_created_at TIMESTAMPTZ NOT NULL,
    article_updated_at TIMESTAMPTZ NOT NULL,
    
    -- Sync metadata
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, platform, article_id)
);

CREATE INDEX idx_article_meta_tenant_date ON article_metadata(tenant_id, article_created_at DESC);
CREATE INDEX idx_article_meta_folder ON article_metadata(tenant_id, folder_id);
CREATE INDEX idx_article_meta_category ON article_metadata(tenant_id, category_id);

-- ============================================
-- Row Level Security (RLS)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_platforms ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_metadata ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own tenant's data
-- Note: app.current_tenant should be set via SET LOCAL before queries

-- Tenants: Only admins can see all, users see their own
CREATE POLICY tenant_isolation ON tenants
    USING (
        id::text = current_setting('app.current_tenant', true)
        OR current_setting('app.is_admin', true) = 'true'
    );

-- Tenant platforms: Tenant-based isolation
CREATE POLICY tenant_platform_isolation ON tenant_platforms
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- Ticket metadata: Tenant-based isolation  
CREATE POLICY ticket_meta_isolation ON ticket_metadata
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- Article metadata: Tenant-based isolation
CREATE POLICY article_meta_isolation ON article_metadata
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- ============================================
-- Helper Functions
-- ============================================

-- Function to get ticket IDs by date range (for hybrid search)
CREATE OR REPLACE FUNCTION get_ticket_ids_by_date(
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
    FROM ticket_metadata tm
    WHERE tm.tenant_id = p_tenant_id
      AND (p_platform IS NULL OR tm.platform = p_platform)
      AND (p_start_date IS NULL OR tm.ticket_created_at >= p_start_date)
      AND (p_end_date IS NULL OR tm.ticket_created_at <= p_end_date)
    ORDER BY tm.ticket_created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get tenant by domain
CREATE OR REPLACE FUNCTION get_tenant_by_domain(p_domain VARCHAR)
RETURNS TABLE(
    tenant_id UUID,
    tenant_slug VARCHAR,
    platform VARCHAR,
    enabled BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT t.id, t.slug, tp.platform, tp.enabled
    FROM tenants t
    JOIN tenant_platforms tp ON t.id = tp.tenant_id
    WHERE tp.domain = p_domain
      AND t.deleted_at IS NULL
      AND tp.enabled = TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- Seed Data (Example)
-- ============================================

-- Insert example tenant
INSERT INTO tenants (slug, name, plan, use_shared_stores)
VALUES ('wedosoft', 'WeDoSoft', 'enterprise', TRUE)
ON CONFLICT (slug) DO NOTHING;

-- Insert platform configuration for the tenant
INSERT INTO tenant_platforms (tenant_id, platform, domain, enabled)
SELECT id, 'freshdesk', 'wedosoft.freshdesk.com', TRUE
FROM tenants WHERE slug = 'wedosoft'
ON CONFLICT (tenant_id, platform) DO NOTHING;
