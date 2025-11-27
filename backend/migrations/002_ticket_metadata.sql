-- ============================================
-- Ticket/Article Metadata Tables for Agent Platform
-- 목적: Gemini 검색 전 날짜/상태 사전 필터링
-- ============================================

-- 1. Tenants 테이블 (멀티테넌시)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,  -- 'wedosoft', 'acme' 등
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'basic',  -- 'basic', 'pro', 'enterprise'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Ticket Metadata 테이블
CREATE TABLE IF NOT EXISTS ticket_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,  -- 'freshdesk', 'zendesk', etc.
    ticket_id INTEGER NOT NULL,
    external_id TEXT,
    status TEXT,
    priority TEXT,
    source TEXT,
    requester TEXT,
    requester_id INTEGER,
    responder TEXT,
    responder_id INTEGER,
    group_name TEXT,
    group_id INTEGER,
    tags TEXT[],
    ticket_created_at TIMESTAMPTZ,
    ticket_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint for upsert
    UNIQUE(tenant_id, platform, ticket_id)
);

-- 3. Article Metadata 테이블
CREATE TABLE IF NOT EXISTS article_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    external_id TEXT,
    title TEXT,
    folder_id INTEGER,
    folder_name TEXT,
    category_id INTEGER,
    category_name TEXT,
    status TEXT,
    article_created_at TIMESTAMPTZ,
    article_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint for upsert
    UNIQUE(tenant_id, platform, article_id)
);

-- ============================================
-- Indexes for Query Performance
-- ============================================

-- Ticket Metadata Indexes
CREATE INDEX IF NOT EXISTS idx_ticket_metadata_tenant_platform 
    ON ticket_metadata(tenant_id, platform);

CREATE INDEX IF NOT EXISTS idx_ticket_metadata_created_at 
    ON ticket_metadata(ticket_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ticket_metadata_updated_at 
    ON ticket_metadata(ticket_updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ticket_metadata_status 
    ON ticket_metadata(tenant_id, platform, status);

CREATE INDEX IF NOT EXISTS idx_ticket_metadata_priority 
    ON ticket_metadata(tenant_id, platform, priority);

CREATE INDEX IF NOT EXISTS idx_ticket_metadata_requester 
    ON ticket_metadata(tenant_id, platform, requester);

CREATE INDEX IF NOT EXISTS idx_ticket_metadata_responder 
    ON ticket_metadata(tenant_id, platform, responder);

-- Article Metadata Indexes
CREATE INDEX IF NOT EXISTS idx_article_metadata_tenant_platform 
    ON article_metadata(tenant_id, platform);

CREATE INDEX IF NOT EXISTS idx_article_metadata_created_at 
    ON article_metadata(article_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_article_metadata_updated_at 
    ON article_metadata(article_updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_article_metadata_folder 
    ON article_metadata(tenant_id, platform, folder_id);

CREATE INDEX IF NOT EXISTS idx_article_metadata_category 
    ON article_metadata(tenant_id, platform, category_id);

-- ============================================
-- Row Level Security (RLS)
-- ============================================

-- Enable RLS
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_metadata ENABLE ROW LEVEL SECURITY;

-- Service role can do everything
CREATE POLICY "Service role full access on tenants" ON tenants
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access on ticket_metadata" ON ticket_metadata
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access on article_metadata" ON article_metadata
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================
-- Updated_at Trigger
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ticket_metadata_updated_at
    BEFORE UPDATE ON ticket_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_article_metadata_updated_at
    BEFORE UPDATE ON article_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Sample Data (Optional)
-- ============================================

-- Insert default tenant
INSERT INTO tenants (slug, name, plan) 
VALUES ('wedosoft', 'Wedosoft', 'pro')
ON CONFLICT (slug) DO NOTHING;
