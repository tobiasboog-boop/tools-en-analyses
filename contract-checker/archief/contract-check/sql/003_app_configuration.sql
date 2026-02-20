-- ============================================================================
-- App Configuration Table
-- ============================================================================
-- Centrale configuratie tabel voor app-wide settings die je wilt kunnen
-- aanpassen zonder code deployment (via Notifica App admin UI)
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_configuration (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope
    app_id uuid NOT NULL REFERENCES apps(id),
    organization_id uuid REFERENCES organizations(id),  -- NULL = global voor app

    -- Configuration key-value
    config_key varchar(100) NOT NULL,                   -- 'confidence_threshold', 'max_batch_size'
    config_value text NOT NULL,                         -- JSON string of plain value
    value_type varchar(20) DEFAULT 'string',            -- 'string', 'number', 'boolean', 'json'

    -- Metadata
    description text,
    default_value text,
    is_active boolean DEFAULT true,
    is_system boolean DEFAULT false,                    -- System configs niet editable via UI

    -- Validation (optional)
    validation_rules jsonb,                             -- {"min": 0, "max": 1, "type": "float"}

    -- Audit
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    updated_by uuid REFERENCES user_profiles(id),

    -- Constraints
    UNIQUE(app_id, organization_id, config_key)
);

COMMENT ON TABLE app_configuration IS 'Centrale app configuratie - editeerbaar via admin UI';
COMMENT ON COLUMN app_configuration.organization_id IS 'NULL = global app setting, specifiek = org override';
COMMENT ON COLUMN app_configuration.is_system IS 'System configs niet editable via UI';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_app_config_app ON app_configuration(app_id);
CREATE INDEX IF NOT EXISTS idx_app_config_key ON app_configuration(app_id, config_key);
CREATE INDEX IF NOT EXISTS idx_app_config_org ON app_configuration(organization_id) WHERE organization_id IS NOT NULL;

-- ============================================================================
-- Seed Data: Contract Checker Configuratie
-- ============================================================================

DO $$
DECLARE
    werkbon_checker_id uuid;
BEGIN
    SELECT id INTO werkbon_checker_id FROM apps WHERE code = 'werkbon-checker';

    IF werkbon_checker_id IS NOT NULL THEN
        -- Classification settings
        INSERT INTO app_configuration (app_id, organization_id, config_key, config_value, value_type, description, default_value, is_system) VALUES
            (werkbon_checker_id, NULL, 'confidence_threshold', '0.85', 'number', 'Minimum confidence score (0-1) voor classificatie. Lagere scores worden ONZEKER.', '0.85', false),
            (werkbon_checker_id, NULL, 'max_batch_size', '100', 'number', 'Maximum aantal werkbonnen per batch classificatie', '100', false),
            (werkbon_checker_id, NULL, 'enable_llm_caching', 'true', 'boolean', 'LLM ready contracts cachen voor snellere classificatie', 'true', false),
            (werkbon_checker_id, NULL, 'classification_timeout_seconds', '30', 'number', 'Timeout voor LLM classificatie calls (seconden)', '30', true)
        ON CONFLICT (app_id, organization_id, config_key) DO NOTHING;

        -- Feature flags
        INSERT INTO app_configuration (app_id, organization_id, config_key, config_value, value_type, description, default_value, is_system) VALUES
            (werkbon_checker_id, NULL, 'feature_quick_classification', 'true', 'boolean', 'Quick Classificatie feature enabled', 'true', false),
            (werkbon_checker_id, NULL, 'feature_contract_generation', 'true', 'boolean', 'LLM Ready Contract Generation enabled', 'true', false),
            (werkbon_checker_id, NULL, 'feature_bedrijfscontext', 'true', 'boolean', 'Bedrijfscontext configuratie enabled', 'true', false)
        ON CONFLICT (app_id, organization_id, config_key) DO NOTHING;

        -- UI settings
        INSERT INTO app_configuration (app_id, organization_id, config_key, config_value, value_type, description, default_value, is_system) VALUES
            (werkbon_checker_id, NULL, 'ui_items_per_page', '50', 'number', 'Aantal items per pagina in tabellen', '50', false),
            (werkbon_checker_id, NULL, 'ui_theme_primary_color', '#667eea', 'string', 'Primary theme color (hex)', '#667eea', false)
        ON CONFLICT (app_id, organization_id, config_key) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- View: Easy Config Lookup
-- ============================================================================

CREATE OR REPLACE VIEW app_configuration_overview AS
SELECT
    c.id,
    a.code as app_code,
    a.name as app_name,
    o.name as organization_name,
    c.config_key,
    c.config_value,
    c.value_type,
    c.description,
    c.is_active,
    c.is_system,
    c.updated_at
FROM app_configuration c
JOIN apps a ON c.app_id = a.id
LEFT JOIN organizations o ON c.organization_id = o.id
WHERE c.is_active = true
ORDER BY a.code, c.config_key;

COMMENT ON VIEW app_configuration_overview IS 'App configuratie overzicht voor admin UI';

-- ============================================================================
-- Helper Function: Get Config Value
-- ============================================================================

CREATE OR REPLACE FUNCTION get_app_config(
    p_app_code varchar,
    p_config_key varchar,
    p_organization_id uuid DEFAULT NULL
) RETURNS text AS $$
DECLARE
    v_value text;
    v_app_id uuid;
BEGIN
    -- Get app_id
    SELECT id INTO v_app_id FROM apps WHERE code = p_app_code;

    IF v_app_id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Try organization-specific config first
    IF p_organization_id IS NOT NULL THEN
        SELECT config_value INTO v_value
        FROM app_configuration
        WHERE app_id = v_app_id
          AND organization_id = p_organization_id
          AND config_key = p_config_key
          AND is_active = true;

        IF v_value IS NOT NULL THEN
            RETURN v_value;
        END IF;
    END IF;

    -- Fallback to global config
    SELECT config_value INTO v_value
    FROM app_configuration
    WHERE app_id = v_app_id
      AND organization_id IS NULL
      AND config_key = p_config_key
      AND is_active = true;

    RETURN v_value;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_app_config IS 'Get app config value with org-specific fallback to global';

-- Example usage:
-- SELECT get_app_config('werkbon-checker', 'confidence_threshold');
-- SELECT get_app_config('werkbon-checker', 'confidence_threshold', 'org-uuid');

-- ============================================================================
-- RLS Policies
-- ============================================================================

ALTER TABLE app_configuration ENABLE ROW LEVEL SECURITY;

-- Users can view configs for their org
CREATE POLICY app_config_org_access ON app_configuration
    FOR SELECT
    USING (
        organization_id IS NULL OR
        organization_id IN (
            SELECT organization_id FROM user_profiles WHERE id = auth.uid()
        )
    );

-- Service role has full access
CREATE POLICY app_config_service_access ON app_configuration
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- ============================================================================
-- Verification
-- ============================================================================

-- Check configs voor werkbon-checker
SELECT
    config_key,
    config_value,
    value_type,
    description
FROM app_configuration_overview
WHERE app_code = 'werkbon-checker'
ORDER BY config_key;

-- ============================================================================
-- COMPLETE!
-- ============================================================================
