-- LLM Configuration & Usage Tracking - Supabase Schema
-- Execute this in Supabase SQL Editor to create the tables

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- TABLE: llm_configurations
-- Stores LLM provider configurations for different clients and action types
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Client & Action Scope
    client_id VARCHAR(50),  -- NULL = default for all clients, specific value = client override
    action_type VARCHAR(100) NOT NULL,  -- 'contract_generation', 'werkbon_classification', etc.

    -- Model Configuration
    provider VARCHAR(50) NOT NULL,  -- 'anthropic', 'mistral', 'openai', 'local'
    model_name VARCHAR(200) NOT NULL,  -- 'claude-sonnet-4-20250514', 'mistral-large', etc.
    model_alias VARCHAR(100),  -- Human-readable name: 'Claude Sonnet 4', 'Local Mistral'

    -- API Configuration
    api_endpoint VARCHAR(500),  -- For local/custom endpoints
    api_key_env_var VARCHAR(100),  -- Name of env var containing API key

    -- Model Parameters
    max_tokens INTEGER DEFAULT 1024,
    temperature DECIMAL(3,2) DEFAULT 0.0,
    additional_params JSONB,  -- For provider-specific params

    -- Cost Configuration (per 1M tokens)
    cost_per_input_token DECIMAL(10,6),
    cost_per_output_token DECIMAL(10,6),
    currency VARCHAR(3) DEFAULT 'EUR',

    -- Status & Metadata
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,  -- Higher priority = preferred when multiple matches
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),

    -- Constraints
    UNIQUE(client_id, action_type, provider, model_name),
    CHECK (temperature >= 0 AND temperature <= 2),
    CHECK (max_tokens > 0),
    CHECK (cost_per_input_token >= 0),
    CHECK (cost_per_output_token >= 0)
);

-- Indexes for efficient lookups
CREATE INDEX idx_llm_config_client_action ON llm_configurations(client_id, action_type);
CREATE INDEX idx_llm_config_active ON llm_configurations(is_active, priority DESC);
CREATE INDEX idx_llm_config_action ON llm_configurations(action_type);

-- Comments for documentation
COMMENT ON TABLE llm_configurations IS 'LLM provider configurations for different clients and action types';
COMMENT ON COLUMN llm_configurations.client_id IS 'NULL for default config, specific value for client override';
COMMENT ON COLUMN llm_configurations.action_type IS 'Action type: contract_generation, werkbon_classification, etc.';
COMMENT ON COLUMN llm_configurations.priority IS 'Higher priority config is preferred when multiple matches exist';

-- =============================================================================
-- TABLE: llm_usage_logs
-- Tracks every LLM API call with token counts and costs
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Configuration Reference
    config_id UUID REFERENCES llm_configurations(id) ON DELETE SET NULL,

    -- Request Context
    client_id VARCHAR(50),
    action_type VARCHAR(100) NOT NULL,
    request_id VARCHAR(100),  -- For correlating multiple API calls

    -- Model Used (denormalized for historical tracking)
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(200) NOT NULL,

    -- Token Usage
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    -- Cost Calculation
    input_cost DECIMAL(12,6),
    output_cost DECIMAL(12,6),
    total_cost DECIMAL(12,6) GENERATED ALWAYS AS (input_cost + output_cost) STORED,
    currency VARCHAR(3) DEFAULT 'EUR',

    -- Performance Metrics
    latency_ms INTEGER,  -- Response time in milliseconds
    success BOOLEAN DEFAULT true,
    error_message TEXT,

    -- Additional Context
    user_id VARCHAR(100),  -- Who triggered the request
    werkbon_id VARCHAR(100),  -- For werkbon classification tracking
    contract_id VARCHAR(100),  -- For contract processing tracking
    metadata JSONB,  -- Additional contextual data

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CHECK (input_tokens >= 0),
    CHECK (output_tokens >= 0),
    CHECK (latency_ms >= 0),
    CHECK (input_cost >= 0),
    CHECK (output_cost >= 0)
);

-- Indexes for common queries
CREATE INDEX idx_llm_usage_client_date ON llm_usage_logs(client_id, created_at DESC);
CREATE INDEX idx_llm_usage_action_date ON llm_usage_logs(action_type, created_at DESC);
CREATE INDEX idx_llm_usage_config ON llm_usage_logs(config_id, created_at DESC);
CREATE INDEX idx_llm_usage_request ON llm_usage_logs(request_id);
CREATE INDEX idx_llm_usage_werkbon ON llm_usage_logs(werkbon_id) WHERE werkbon_id IS NOT NULL;
CREATE INDEX idx_llm_usage_contract ON llm_usage_logs(contract_id) WHERE contract_id IS NOT NULL;
CREATE INDEX idx_llm_usage_date ON llm_usage_logs(created_at DESC);
CREATE INDEX idx_llm_usage_success ON llm_usage_logs(success, created_at DESC);

-- Comments for documentation
COMMENT ON TABLE llm_usage_logs IS 'Logs of all LLM API calls with token usage and costs';
COMMENT ON COLUMN llm_usage_logs.total_tokens IS 'Computed column: input_tokens + output_tokens';
COMMENT ON COLUMN llm_usage_logs.total_cost IS 'Computed column: input_cost + output_cost';

-- =============================================================================
-- MATERIALIZED VIEW: llm_usage_summary
-- Pre-aggregated statistics for reporting
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS llm_usage_summary AS
SELECT
    client_id,
    action_type,
    provider,
    model_name,
    DATE(created_at) as usage_date,

    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_tokens) as total_tokens,

    SUM(total_cost) as total_cost,
    AVG(total_cost) as avg_cost_per_request,
    currency,

    AVG(latency_ms) as avg_latency_ms,
    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as error_count,

    MIN(created_at) as first_request,
    MAX(created_at) as last_request

FROM llm_usage_logs
GROUP BY client_id, action_type, provider, model_name, DATE(created_at), currency;

CREATE INDEX idx_llm_summary_date ON llm_usage_summary(usage_date DESC);
CREATE INDEX idx_llm_summary_client ON llm_usage_summary(client_id, usage_date DESC);
CREATE INDEX idx_llm_summary_action ON llm_usage_summary(action_type, usage_date DESC);

COMMENT ON MATERIALIZED VIEW llm_usage_summary IS 'Daily aggregated statistics for LLM usage';

-- =============================================================================
-- FUNCTION: Refresh materialized view (call daily via cron)
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_llm_usage_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW llm_usage_summary;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_llm_usage_summary IS 'Refresh daily usage summary - schedule via pg_cron';

-- =============================================================================
-- SAMPLE DATA: Default Configurations
-- =============================================================================

-- Default: Contract Generation uses Claude (heavy lifting)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_key_env_var, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency,
    priority, notes
) VALUES (
    NULL, 'contract_generation', 'anthropic', 'claude-sonnet-4-20250514', 'Claude Sonnet 4',
    'ANTHROPIC_API_KEY', 4096, 0.0,
    3.00, 15.00, 'EUR',
    100, 'Default heavy model for contract processing'
)
ON CONFLICT (client_id, action_type, provider, model_name) DO NOTHING;

-- Default: Werkbon Classification uses Mistral (cost-effective bulk work)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_endpoint, api_key_env_var, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency,
    priority, notes
) VALUES (
    NULL, 'werkbon_classification', 'mistral', 'mistral-large-latest', 'Mistral Large',
    'https://api.mistral.ai/v1/chat/completions', 'MISTRAL_API_KEY', 1024, 0.0,
    0.80, 2.40, 'EUR',
    100, 'Cost-effective model for bulk werkbon classification'
)
ON CONFLICT (client_id, action_type, provider, model_name) DO NOTHING;

-- Alternative: Local Mistral (inactive by default, activate when local server ready)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_endpoint, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency,
    priority, is_active, notes
) VALUES (
    NULL, 'werkbon_classification', 'local', 'mistral-7b-instruct', 'Local Mistral 7B',
    'http://localhost:11434/v1/chat/completions', 1024, 0.0,
    0.00, 0.00, 'EUR',
    50, false, 'Local model for zero-cost bulk processing (activate when deployed)'
)
ON CONFLICT (client_id, action_type, provider, model_name) DO NOTHING;

-- =============================================================================
-- ROW LEVEL SECURITY (Optional, enable if multi-tenant)
-- =============================================================================

-- Enable RLS
-- ALTER TABLE llm_configurations ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE llm_usage_logs ENABLE ROW LEVEL SECURITY;

-- Example policy: Users can only see their own client's data
-- CREATE POLICY client_access ON llm_configurations
--     FOR SELECT
--     USING (client_id = current_setting('app.current_client_id', true));

-- CREATE POLICY client_usage_access ON llm_usage_logs
--     FOR SELECT
--     USING (client_id = current_setting('app.current_client_id', true));

-- =============================================================================
-- GRANTS (Adjust based on your security model)
-- =============================================================================

-- Grant service role full access (for backend operations)
-- GRANT ALL ON llm_configurations TO service_role;
-- GRANT ALL ON llm_usage_logs TO service_role;
-- GRANT ALL ON llm_usage_summary TO service_role;

-- Grant anon/authenticated read-only access (for dashboard)
-- GRANT SELECT ON llm_configurations TO anon, authenticated;
-- GRANT SELECT ON llm_usage_logs TO anon, authenticated;
-- GRANT SELECT ON llm_usage_summary TO anon, authenticated;

-- =============================================================================
-- COMPLETE!
-- =============================================================================

-- Verify tables created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('llm_configurations', 'llm_usage_logs')
ORDER BY table_name;
