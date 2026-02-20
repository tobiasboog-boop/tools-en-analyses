-- ============================================================================
-- Notifica App - LLM Configuration & Usage Tracking
-- ============================================================================
-- Integreert met bestaande schema (001_extend_schema.sql)
-- Voegt LLM configuratie en usage tracking toe voor alle apps
--
-- Bestaande tabellen die we gebruiken:
-- - apps (voor application_id koppelingen)
-- - organizations (voor multi-tenant)
-- - user_profiles (voor audit)
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. LLM PROVIDERS (Registry van beschikbare providers)
-- ============================================================================
-- Centrale registry van alle LLM providers die we kunnen gebruiken

CREATE TABLE IF NOT EXISTS llm_providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identificatie
    code varchar(50) NOT NULL UNIQUE,              -- 'anthropic', 'mistral', 'openai', 'local'
    name varchar(100) NOT NULL,                    -- 'Anthropic (Claude)', 'Mistral AI'
    description text,

    -- Default configuratie
    default_api_endpoint varchar(500),             -- API endpoint URL
    api_key_env_var varchar(100),                  -- Env var naam voor API key
    supports_streaming boolean DEFAULT false,

    -- Status
    is_active boolean DEFAULT true,
    is_external boolean DEFAULT true,              -- false voor local/self-hosted

    -- Metadata
    website_url varchar(500),
    documentation_url varchar(500),
    notes text,

    -- Timestamps
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

COMMENT ON TABLE llm_providers IS 'Registry van beschikbare LLM providers (Claude, Mistral, OpenAI, Local)';

-- Index
CREATE INDEX IF NOT EXISTS idx_llm_providers_active ON llm_providers(is_active);

-- ============================================================================
-- 2. LLM MODELS (Registry van beschikbare modellen per provider)
-- ============================================================================
-- Centrale registry van alle LLM modellen

CREATE TABLE IF NOT EXISTS llm_models (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Koppeling
    provider_id uuid NOT NULL REFERENCES llm_providers(id),

    -- Identificatie
    model_code varchar(200) NOT NULL,              -- 'claude-sonnet-4-20250514', 'mistral-large-latest'
    model_name varchar(200) NOT NULL,              -- 'Claude Sonnet 4', 'Mistral Large'
    model_version varchar(50),                     -- '4.0', 'latest'

    -- Capabilities
    max_tokens_input integer,                      -- Max input tokens
    max_tokens_output integer,                     -- Max output tokens
    supports_function_calling boolean DEFAULT false,
    supports_vision boolean DEFAULT false,

    -- Pricing (per 1M tokens in EUR)
    cost_per_input_token numeric(10,6),
    cost_per_output_token numeric(10,6),
    currency varchar(3) DEFAULT 'EUR',

    -- Status
    is_active boolean DEFAULT true,
    is_recommended boolean DEFAULT false,          -- Aanbevolen voor gebruik?

    -- Metadata
    release_date date,
    deprecation_date date,
    notes text,

    -- Timestamps
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),

    -- Unique per provider
    UNIQUE(provider_id, model_code)
);

COMMENT ON TABLE llm_models IS 'Registry van beschikbare LLM modellen met pricing en capabilities';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models(provider_id);
CREATE INDEX IF NOT EXISTS idx_llm_models_active ON llm_models(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_models_recommended ON llm_models(is_recommended) WHERE is_recommended = true;

-- ============================================================================
-- 3. LLM CONFIGURATIONS (Welk model voor welke app/klant/actie)
-- ============================================================================
-- Configuratie: welk LLM model gebruiken voor welke app, klant, en actie

CREATE TABLE IF NOT EXISTS llm_configurations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope: App + Organization + Action
    app_id uuid NOT NULL REFERENCES apps(id),
    organization_id uuid REFERENCES organizations(id),  -- NULL = default voor alle klanten
    action_type varchar(100) NOT NULL,             -- 'contract_generation', 'werkbon_classification'

    -- Model selectie
    model_id uuid NOT NULL REFERENCES llm_models(id),

    -- Model parameters
    max_tokens integer DEFAULT 1024,
    temperature numeric(3,2) DEFAULT 0.0,
    top_p numeric(3,2),
    additional_params jsonb,                       -- Provider-specific parameters

    -- Custom endpoint (voor local/custom deployments)
    custom_api_endpoint varchar(500),              -- Overschrijft provider default

    -- Priority en status
    priority integer DEFAULT 100,                  -- Hogere priority = preferred
    is_active boolean DEFAULT true,

    -- Metadata
    notes text,
    configured_by uuid REFERENCES user_profiles(id),

    -- Timestamps
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),

    -- Constraints
    CHECK (temperature >= 0 AND temperature <= 2),
    CHECK (max_tokens > 0),
    CHECK (priority >= 0),

    -- Unique config per app/org/action/model
    UNIQUE(app_id, organization_id, action_type, model_id)
);

COMMENT ON TABLE llm_configurations IS 'LLM configuratie per app, organisatie en actie type';
COMMENT ON COLUMN llm_configurations.organization_id IS 'NULL = default voor alle klanten';
COMMENT ON COLUMN llm_configurations.priority IS 'Hogere waarde = preferred bij meerdere matches';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_config_app_org_action ON llm_configurations(app_id, organization_id, action_type);
CREATE INDEX IF NOT EXISTS idx_llm_config_app_action ON llm_configurations(app_id, action_type);
CREATE INDEX IF NOT EXISTS idx_llm_config_model ON llm_configurations(model_id);
CREATE INDEX IF NOT EXISTS idx_llm_config_active ON llm_configurations(is_active, priority DESC);

-- ============================================================================
-- 4. LLM USAGE LOGS (Tracking van alle LLM calls)
-- ============================================================================
-- Logt elke LLM API call voor cost tracking en analytics

CREATE TABLE IF NOT EXISTS llm_usage_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Configuration reference
    config_id uuid REFERENCES llm_configurations(id) ON DELETE SET NULL,

    -- Context: Welke app, klant, actie
    app_id uuid NOT NULL REFERENCES apps(id),
    organization_id uuid REFERENCES organizations(id),
    action_type varchar(100) NOT NULL,
    request_id varchar(100),                       -- Voor correlatie van multiple calls

    -- Model used (denormalized voor historical tracking)
    provider_id uuid REFERENCES llm_providers(id) ON DELETE SET NULL,
    model_id uuid REFERENCES llm_models(id) ON DELETE SET NULL,
    provider_code varchar(50) NOT NULL,            -- Denormalized: 'anthropic', 'mistral'
    model_code varchar(200) NOT NULL,              -- Denormalized: 'claude-sonnet-4-20250514'

    -- Token usage
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    total_tokens integer GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    -- Cost calculation
    input_cost numeric(12,6),
    output_cost numeric(12,6),
    total_cost numeric(12,6) GENERATED ALWAYS AS (input_cost + output_cost) STORED,
    currency varchar(3) DEFAULT 'EUR',

    -- Performance metrics
    latency_ms integer,                            -- Response time
    success boolean DEFAULT true,
    error_message text,
    http_status_code integer,

    -- User context
    user_id uuid REFERENCES user_profiles(id) ON DELETE SET NULL,
    user_email varchar(255),                       -- Backup if user deleted

    -- Entity context (flexible per app)
    entity_type varchar(50),                       -- 'werkbon', 'contract', 'incident'
    entity_id varchar(100),                        -- Entity identifier
    metadata jsonb,                                -- Extra contextual data

    -- Legacy compatibility (specifiek voor contract-checker)
    werkbon_id varchar(100),
    contract_id varchar(100),

    -- Timestamp
    created_at timestamp with time zone DEFAULT now(),

    -- Constraints
    CHECK (input_tokens >= 0),
    CHECK (output_tokens >= 0),
    CHECK (latency_ms >= 0),
    CHECK (input_cost >= 0),
    CHECK (output_cost >= 0)
);

COMMENT ON TABLE llm_usage_logs IS 'Audit log van alle LLM API calls met cost en performance tracking';
COMMENT ON COLUMN llm_usage_logs.entity_type IS 'Generic entity type voor flexible tracking per app';

-- Indexes voor common queries
CREATE INDEX IF NOT EXISTS idx_llm_usage_app_date ON llm_usage_logs(app_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_app_org_date ON llm_usage_logs(app_id, organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_app_action_date ON llm_usage_logs(app_id, action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_config ON llm_usage_logs(config_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_request ON llm_usage_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_user ON llm_usage_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_entity ON llm_usage_logs(app_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_date ON llm_usage_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_success ON llm_usage_logs(success, created_at DESC);

-- Legacy compatibility indexes
CREATE INDEX IF NOT EXISTS idx_llm_usage_werkbon ON llm_usage_logs(werkbon_id) WHERE werkbon_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_llm_usage_contract ON llm_usage_logs(contract_id) WHERE contract_id IS NOT NULL;

-- ============================================================================
-- 5. MATERIALIZED VIEW: Usage Summary per App/Org/Day
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS llm_usage_summary AS
SELECT
    app_id,
    organization_id,
    action_type,
    provider_code,
    model_code,
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
GROUP BY app_id, organization_id, action_type, provider_code, model_code, DATE(created_at), currency;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_summary_app_date ON llm_usage_summary(app_id, usage_date DESC);
CREATE INDEX IF NOT EXISTS idx_llm_summary_app_org ON llm_usage_summary(app_id, organization_id, usage_date DESC);
CREATE INDEX IF NOT EXISTS idx_llm_summary_date ON llm_usage_summary(usage_date DESC);

COMMENT ON MATERIALIZED VIEW llm_usage_summary IS 'Daily aggregated LLM usage statistics per app and organization';

-- ============================================================================
-- 6. VIEWS: Easy access views
-- ============================================================================

-- Configurations met model en provider details
CREATE OR REPLACE VIEW llm_configurations_overview AS
SELECT
    c.id,
    c.app_id,
    a.name as app_name,
    c.organization_id,
    o.name as organization_name,
    c.action_type,
    c.priority,
    c.is_active,
    m.model_code,
    m.model_name,
    p.code as provider_code,
    p.name as provider_name,
    c.max_tokens,
    c.temperature,
    m.cost_per_input_token,
    m.cost_per_output_token,
    c.created_at,
    c.updated_at
FROM llm_configurations c
JOIN llm_models m ON c.model_id = m.id
JOIN llm_providers p ON m.provider_id = p.id
JOIN apps a ON c.app_id = a.id
LEFT JOIN organizations o ON c.organization_id = o.id;

COMMENT ON VIEW llm_configurations_overview IS 'LLM configuraties met alle details voor easy querying';

-- Recent usage per app
CREATE OR REPLACE VIEW llm_recent_usage AS
SELECT
    l.id,
    l.app_id,
    a.name as app_name,
    l.organization_id,
    o.name as organization_name,
    l.action_type,
    l.provider_code,
    l.model_code,
    l.input_tokens,
    l.output_tokens,
    l.total_cost,
    l.latency_ms,
    l.success,
    l.user_id,
    up.full_name as user_name,
    l.created_at
FROM llm_usage_logs l
JOIN apps a ON l.app_id = a.id
LEFT JOIN organizations o ON l.organization_id = o.id
LEFT JOIN user_profiles up ON l.user_id = up.id
ORDER BY l.created_at DESC
LIMIT 1000;

COMMENT ON VIEW llm_recent_usage IS 'Recent 1000 LLM API calls met details';

-- Cost overview per organization
CREATE OR REPLACE VIEW llm_cost_per_organization AS
SELECT
    l.organization_id,
    o.name as organization_name,
    l.app_id,
    a.name as app_name,
    DATE_TRUNC('month', l.created_at) as month,
    COUNT(*) as total_requests,
    SUM(l.total_tokens) as total_tokens,
    SUM(l.total_cost) as total_cost,
    l.currency
FROM llm_usage_logs l
JOIN apps a ON l.app_id = a.id
LEFT JOIN organizations o ON l.organization_id = o.id
WHERE l.success = true
GROUP BY l.organization_id, o.name, l.app_id, a.name, DATE_TRUNC('month', l.created_at), l.currency
ORDER BY month DESC, total_cost DESC;

COMMENT ON VIEW llm_cost_per_organization IS 'Maandelijkse LLM kosten per organisatie en app';

-- ============================================================================
-- 7. FUNCTIONS: Refresh materialized view
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_llm_usage_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW llm_usage_summary;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_llm_usage_summary IS 'Refresh daily usage summary - run via cron';

-- ============================================================================
-- 8. SEED DATA: Providers en Models
-- ============================================================================

-- Providers
INSERT INTO llm_providers (code, name, description, default_api_endpoint, api_key_env_var, is_active, is_external) VALUES
    ('anthropic', 'Anthropic (Claude)', 'Anthropic Claude API - Premium kwaliteit', 'https://api.anthropic.com/v1/messages', 'ANTHROPIC_API_KEY', true, true),
    ('mistral', 'Mistral AI', 'Mistral API - Cost-effectief Europees alternatief', 'https://api.mistral.ai/v1/chat/completions', 'MISTRAL_API_KEY', true, true),
    ('openai', 'OpenAI', 'OpenAI GPT modellen', 'https://api.openai.com/v1/chat/completions', 'OPENAI_API_KEY', true, true),
    ('local', 'Local/Self-Hosted', 'Self-hosted modellen via Ollama/vLLM', 'http://localhost:11434/v1/chat/completions', NULL, true, false)
ON CONFLICT (code) DO NOTHING;

-- Models (voorbeelden)
DO $$
DECLARE
    anthropic_id uuid;
    mistral_id uuid;
    openai_id uuid;
    local_id uuid;
BEGIN
    -- Get provider IDs
    SELECT id INTO anthropic_id FROM llm_providers WHERE code = 'anthropic';
    SELECT id INTO mistral_id FROM llm_providers WHERE code = 'mistral';
    SELECT id INTO openai_id FROM llm_providers WHERE code = 'openai';
    SELECT id INTO local_id FROM llm_providers WHERE code = 'local';

    -- Anthropic models
    INSERT INTO llm_models (provider_id, model_code, model_name, max_tokens_input, max_tokens_output, cost_per_input_token, cost_per_output_token, is_active, is_recommended) VALUES
        (anthropic_id, 'claude-sonnet-4-20250514', 'Claude Sonnet 4', 200000, 8096, 3.00, 15.00, true, true),
        (anthropic_id, 'claude-opus-4-5-20251101', 'Claude Opus 4.5', 200000, 16384, 15.00, 75.00, true, false)
    ON CONFLICT (provider_id, model_code) DO NOTHING;

    -- Mistral models
    INSERT INTO llm_models (provider_id, model_code, model_name, max_tokens_input, max_tokens_output, cost_per_input_token, cost_per_output_token, is_active, is_recommended) VALUES
        (mistral_id, 'mistral-large-latest', 'Mistral Large', 128000, 4096, 0.80, 2.40, true, true),
        (mistral_id, 'mistral-small-latest', 'Mistral Small', 128000, 4096, 0.20, 0.60, true, false)
    ON CONFLICT (provider_id, model_code) DO NOTHING;

    -- OpenAI models
    INSERT INTO llm_models (provider_id, model_code, model_name, max_tokens_input, max_tokens_output, cost_per_input_token, cost_per_output_token, is_active, is_recommended) VALUES
        (openai_id, 'gpt-4-turbo-preview', 'GPT-4 Turbo', 128000, 4096, 10.00, 30.00, true, false),
        (openai_id, 'gpt-3.5-turbo', 'GPT-3.5 Turbo', 16385, 4096, 0.50, 1.50, true, false)
    ON CONFLICT (provider_id, model_code) DO NOTHING;

    -- Local models
    INSERT INTO llm_models (provider_id, model_code, model_name, max_tokens_input, max_tokens_output, cost_per_input_token, cost_per_output_token, is_active, is_recommended) VALUES
        (local_id, 'mistral-7b-instruct', 'Mistral 7B Instruct (Local)', 8192, 2048, 0.00, 0.00, false, false),
        (local_id, 'llama-3-70b', 'Llama 3 70B (Local)', 8192, 4096, 0.00, 0.00, false, false)
    ON CONFLICT (provider_id, model_code) DO NOTHING;
END $$;

-- ============================================================================
-- 9. SEED DATA: Default configurations voor Contract Checker
-- ============================================================================

DO $$
DECLARE
    contract_checker_id uuid;
    claude_sonnet_id uuid;
    mistral_large_id uuid;
BEGIN
    -- Get app and model IDs
    SELECT id INTO contract_checker_id FROM apps WHERE code = 'werkbon-checker';
    SELECT id INTO claude_sonnet_id FROM llm_models WHERE model_code = 'claude-sonnet-4-20250514';
    SELECT id INTO mistral_large_id FROM llm_models WHERE model_code = 'mistral-large-latest';

    -- Alleen als contract checker app bestaat
    IF contract_checker_id IS NOT NULL THEN
        -- Contract generation: Claude (heavy lifting)
        IF claude_sonnet_id IS NOT NULL THEN
            INSERT INTO llm_configurations (app_id, organization_id, action_type, model_id, max_tokens, temperature, priority, notes) VALUES
                (contract_checker_id, NULL, 'contract_generation', claude_sonnet_id, 4096, 0.0, 100, 'Default: Claude voor contract processing')
            ON CONFLICT (app_id, organization_id, action_type, model_id) DO NOTHING;
        END IF;

        -- Werkbon classification: Mistral (cost-effective)
        IF mistral_large_id IS NOT NULL THEN
            INSERT INTO llm_configurations (app_id, organization_id, action_type, model_id, max_tokens, temperature, priority, notes) VALUES
                (contract_checker_id, NULL, 'werkbon_classification', mistral_large_id, 1024, 0.0, 100, 'Default: Mistral voor bulk werkbon classificatie')
            ON CONFLICT (app_id, organization_id, action_type, model_id) DO NOTHING;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- 10. ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE llm_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_usage_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view configs for their org
CREATE POLICY llm_config_org_access ON llm_configurations
    FOR SELECT
    USING (
        organization_id IS NULL OR
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE id = auth.uid()
        )
    );

-- Policy: Users can view usage logs for their org
CREATE POLICY llm_usage_org_access ON llm_usage_logs
    FOR SELECT
    USING (
        organization_id IS NULL OR
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE id = auth.uid()
        )
    );

-- Policy: Service role has full access
CREATE POLICY llm_config_service_access ON llm_configurations
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

CREATE POLICY llm_usage_service_access ON llm_usage_logs
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify tables created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name LIKE 'llm_%'
ORDER BY table_name;

-- Show providers and models
SELECT
    p.name as provider,
    COUNT(m.id) as model_count,
    ARRAY_AGG(m.model_name) as models
FROM llm_providers p
LEFT JOIN llm_models m ON p.id = m.provider_id AND m.is_active = true
GROUP BY p.id, p.name
ORDER BY p.name;

-- Show default configurations
SELECT
    a.name as app,
    c.action_type,
    m.model_name,
    p.name as provider,
    c.priority
FROM llm_configurations c
JOIN apps a ON c.app_id = a.id
JOIN llm_models m ON c.model_id = m.id
JOIN llm_providers p ON m.provider_id = p.id
WHERE c.organization_id IS NULL
ORDER BY a.name, c.action_type;

-- ============================================================================
-- COMPLETE!
-- ============================================================================
