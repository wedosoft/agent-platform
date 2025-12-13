-- Migration: Cache tenant ticket fields schema
-- Date: 2025-12-13
-- Description: Persist Freshdesk/Zendesk ticket field schema per tenant for faster app boot

-- ============================================
-- Tenant Ticket Fields Cache Table
-- ============================================

CREATE TABLE IF NOT EXISTS tenant_ticket_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('freshdesk', 'zendesk', 'intercom', 'web', 'api')),

    -- Raw /ticket_fields payload (array of field definitions)
    ticket_fields JSONB NOT NULL,

    -- For change detection / debugging
    schema_hash VARCHAR(64),
    fetched_from_domain VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_tenant_ticket_fields_tenant_platform
    ON tenant_ticket_fields(tenant_id, platform);

CREATE INDEX IF NOT EXISTS idx_tenant_ticket_fields_updated_at
    ON tenant_ticket_fields(updated_at DESC);

-- ============================================
-- Row Level Security (RLS)
-- ============================================

ALTER TABLE tenant_ticket_fields ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_ticket_fields_isolation ON tenant_ticket_fields
    USING (tenant_id::text = current_setting('app.current_tenant', true));
