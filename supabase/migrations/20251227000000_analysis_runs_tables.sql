-- Migration: Create analysis runs and ticket analyses tables
-- Date: 2025-12-27
-- Description: Persistence layer for ticket analysis orchestrator (PR2)

-- ============================================
-- Analysis Runs Table (audit log)
-- ============================================
CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ticket_id VARCHAR(50) NOT NULL,

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    gate VARCHAR(30)
        CHECK (gate IS NULL OR gate IN ('CONFIRM', 'EDIT', 'DECIDE', 'TEACH')),

    -- Metadata
    meta JSONB DEFAULT '{}',
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_analysis_runs_tenant_ticket
    ON analysis_runs(tenant_id, ticket_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
    ON analysis_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status
    ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_gate
    ON analysis_runs(gate) WHERE gate IS NOT NULL;

-- ============================================
-- Ticket Analyses Table (analysis results)
-- ============================================
CREATE TABLE IF NOT EXISTS ticket_analyses (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ticket_id VARCHAR(50) NOT NULL,

    -- Core analysis content
    narrative TEXT,
    root_cause TEXT,
    resolution JSONB DEFAULT '[]',
    confidence DECIMAL(3,2) DEFAULT 0.0
        CHECK (confidence >= 0 AND confidence <= 1),

    -- Classification
    intent VARCHAR(50),
    sentiment VARCHAR(20),

    -- Additional analysis data
    open_questions JSONB DEFAULT '[]',
    risk_tags JSONB DEFAULT '[]',
    field_proposals JSONB DEFAULT '[]',
    evidence JSONB DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- One analysis per run
    UNIQUE(run_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ticket_analyses_tenant_ticket
    ON ticket_analyses(tenant_id, ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_analyses_created_at
    ON ticket_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticket_analyses_confidence
    ON ticket_analyses(confidence);
CREATE INDEX IF NOT EXISTS idx_ticket_analyses_intent
    ON ticket_analyses(intent) WHERE intent IS NOT NULL;

-- ============================================
-- Row Level Security (RLS)
-- ============================================
ALTER TABLE analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_analyses ENABLE ROW LEVEL SECURITY;

-- Policies for tenant isolation
DO $$
BEGIN
    -- Drop existing policies if they exist
    DROP POLICY IF EXISTS analysis_runs_tenant_isolation ON analysis_runs;
    DROP POLICY IF EXISTS ticket_analyses_tenant_isolation ON ticket_analyses;

    -- Create new policies
    CREATE POLICY analysis_runs_tenant_isolation ON analysis_runs
        FOR ALL
        USING (tenant_id::text = current_setting('app.current_tenant', true));

    CREATE POLICY ticket_analyses_tenant_isolation ON ticket_analyses
        FOR ALL
        USING (tenant_id::text = current_setting('app.current_tenant', true));
END
$$;

-- ============================================
-- Service role access (bypass RLS)
-- ============================================
GRANT ALL ON analysis_runs TO service_role;
GRANT ALL ON ticket_analyses TO service_role;

-- ============================================
-- Helper function for history lookup
-- ============================================
CREATE OR REPLACE FUNCTION get_ticket_analysis_history(
    p_tenant_id UUID,
    p_ticket_id VARCHAR,
    p_limit INT DEFAULT 10
)
RETURNS TABLE(
    analysis_id UUID,
    gate VARCHAR,
    confidence DECIMAL,
    created_at TIMESTAMPTZ,
    narrative TEXT,
    intent VARCHAR,
    status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ar.id AS analysis_id,
        ar.gate,
        ta.confidence,
        ar.created_at,
        ta.narrative,
        ta.intent,
        ar.status
    FROM analysis_runs ar
    LEFT JOIN ticket_analyses ta ON ta.run_id = ar.id
    WHERE ar.tenant_id = p_tenant_id
      AND ar.ticket_id = p_ticket_id
    ORDER BY ar.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE analysis_runs IS 'Audit log of all ticket analysis attempts';
COMMENT ON TABLE ticket_analyses IS 'Successful ticket analysis results';
COMMENT ON COLUMN analysis_runs.gate IS 'UI mode gate: CONFIRM, EDIT, DECIDE, TEACH';
COMMENT ON COLUMN ticket_analyses.confidence IS 'Analysis confidence score 0.0-1.0';
COMMENT ON COLUMN ticket_analyses.field_proposals IS 'Suggested ticket field updates';
COMMENT ON COLUMN ticket_analyses.evidence IS 'Supporting evidence for analysis claims';
