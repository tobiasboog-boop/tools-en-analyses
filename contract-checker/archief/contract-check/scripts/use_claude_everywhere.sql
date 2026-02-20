-- ============================================================================
-- PILOT QUICK START: Use Claude Everywhere
-- ============================================================================
-- Als je Mistral API key nog niet hebt, gebruik dan voorlopig Claude overal.
-- Je kunt later altijd switchen naar Mistral door deze config te updaten.
-- ============================================================================

-- Update werkbon_classification to use Claude instead of Mistral
UPDATE llm_configurations
SET
    model_id = (
        SELECT id FROM llm_models
        WHERE model_code = 'claude-sonnet-4-20250514'
        LIMIT 1
    ),
    updated_at = NOW()
WHERE action_type = 'werkbon_classification'
  AND organization_id IS NULL;

-- Verify the change
SELECT
    a.name as app_name,
    c.action_type,
    p.name as provider,
    m.model_name,
    c.priority,
    c.updated_at
FROM llm_configurations c
JOIN apps a ON c.app_id = a.id
JOIN llm_models m ON c.model_id = m.id
JOIN llm_providers p ON m.provider_id = p.id
WHERE a.code = 'werkbon-checker'
ORDER BY c.action_type, c.priority DESC;

-- Expected output:
-- app_name                  | action_type              | provider             | model_name         | priority
-- --------------------------|--------------------------|----------------------|--------------------|----------
-- Werkbon Contract Checker  | contract_generation      | Anthropic (Claude)   | Claude Sonnet 4    | 100
-- Werkbon Contract Checker  | werkbon_classification   | Anthropic (Claude)   | Claude Sonnet 4    | 100

-- ============================================================================
-- RESULT: Both actions now use Claude
-- ============================================================================
-- ✅ New LLM system will work immediately
-- ✅ Token tracking will work
-- ✅ No Mistral API key needed
-- ❌ No cost savings yet (still using Claude for everything)
--
-- LATER: When you have Mistral API key, run this to switch back:
--
-- UPDATE llm_configurations
-- SET model_id = (SELECT id FROM llm_models WHERE model_code = 'mistral-large-latest')
-- WHERE action_type = 'werkbon_classification' AND organization_id IS NULL;
-- ============================================================================
