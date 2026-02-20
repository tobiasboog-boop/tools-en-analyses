# LLM Configuration & Usage Tracking - Supabase Schema Design

## Overview

This schema enables flexible LLM provider configuration per client and action type, with comprehensive token usage and cost tracking. The design supports switching between heavy LLMs (Claude) for contract processing and lighter LLMs (Mistral, local models) for bulk werkbon classification.

---

## Schema Design

### Table 1: `llm_configurations`

Stores which LLM model to use for specific clients and action types.

```sql
CREATE TABLE llm_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Client & Action Scope
    client_id VARCHAR(50),  -- NULL = default for all clients, specific = override for client
    action_type VARCHAR(100) NOT NULL,  -- 'contract_generation', 'werkbon_classification', etc.

    -- Model Configuration
    provider VARCHAR(50) NOT NULL,  -- 'anthropic', 'mistral', 'openai', 'local'
    model_name VARCHAR(200) NOT NULL,  -- 'claude-sonnet-4-20250514', 'mistral-large', etc.
    model_alias VARCHAR(100),  -- Human-readable name: 'Claude Sonnet 4', 'Local Mistral'

    -- API Configuration
    api_endpoint VARCHAR(500),  -- For local/custom endpoints
    api_key_env_var VARCHAR(100),  -- Name of env var containing API key: 'ANTHROPIC_API_KEY'

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
    CHECK (max_tokens > 0)
);

-- Indexes
CREATE INDEX idx_llm_config_client_action ON llm_configurations(client_id, action_type);
CREATE INDEX idx_llm_config_active ON llm_configurations(is_active, priority DESC);
```

**Configuration Lookup Strategy:**
1. Check for specific `client_id` + `action_type` match (highest priority)
2. Fallback to `client_id = NULL` + `action_type` match (default for action)
3. Use `priority` field to select when multiple active configs exist

---

### Table 2: `llm_usage_logs`

Tracks every LLM API call with token counts and calculated costs.

```sql
CREATE TABLE llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Configuration Reference
    config_id UUID REFERENCES llm_configurations(id),

    -- Request Context
    client_id VARCHAR(50),
    action_type VARCHAR(100) NOT NULL,
    request_id VARCHAR(100),  -- For correlating multiple API calls in one operation

    -- Model Used (denormalized for historical tracking)
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(200) NOT NULL,

    -- Token Usage
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
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
    CHECK (latency_ms >= 0)
);

-- Indexes for common queries
CREATE INDEX idx_llm_usage_client_date ON llm_usage_logs(client_id, created_at DESC);
CREATE INDEX idx_llm_usage_action_date ON llm_usage_logs(action_type, created_at DESC);
CREATE INDEX idx_llm_usage_config ON llm_usage_logs(config_id, created_at DESC);
CREATE INDEX idx_llm_usage_request ON llm_usage_logs(request_id);
CREATE INDEX idx_llm_usage_werkbon ON llm_usage_logs(werkbon_id) WHERE werkbon_id IS NOT NULL;
```

---

### Table 3: `llm_usage_summary` (Materialized View)

Pre-aggregated statistics for reporting and cost monitoring.

```sql
CREATE MATERIALIZED VIEW llm_usage_summary AS
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

-- Refresh daily via cron or trigger
```

---

## Action Types

Standard action types used in the application:

| Action Type | Description | Current Model | Proposed Model |
|-------------|-------------|---------------|----------------|
| `contract_generation` | Convert raw contracts to LLM-ready format | Claude Sonnet 4 | Claude Sonnet 4 (heavy lifting) |
| `werkbon_classification` | Classify werkbon against contract | Claude Sonnet 4 | **Mistral or Local** (bulk work) |
| `contract_analysis` | Future: Deep contract analysis | - | Claude or specialized model |
| `prompt_optimization` | Future: Optimize classification prompts | - | Claude Opus |

---

## Sample Data

### Default Configuration (no client-specific overrides)

```sql
-- Contract Generation: Use Claude (heavy lifting)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_key_env_var, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency, priority
) VALUES (
    NULL, 'contract_generation', 'anthropic', 'claude-sonnet-4-20250514', 'Claude Sonnet 4',
    'ANTHROPIC_API_KEY', 4096, 0.0,
    3.00, 15.00, 'EUR', 100
);

-- Werkbon Classification: Use Mistral (bulk work, cost-effective)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_endpoint, api_key_env_var, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency, priority
) VALUES (
    NULL, 'werkbon_classification', 'mistral', 'mistral-large-latest', 'Mistral Large',
    'https://api.mistral.ai/v1/chat/completions', 'MISTRAL_API_KEY', 1024, 0.0,
    0.80, 2.40, 'EUR', 100
);

-- Alternative: Local Mistral (for high-volume, zero cost)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_endpoint, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency, priority, is_active
) VALUES (
    NULL, 'werkbon_classification', 'local', 'mistral-7b-instruct', 'Local Mistral 7B',
    'http://localhost:11434/api/chat', 1024, 0.0,
    0.00, 0.00, 'EUR', 50, false  -- Inactive by default, activate when local server ready
);
```

### Client-Specific Override

```sql
-- WVC uses Claude for everything (premium client)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, model_alias,
    api_key_env_var, max_tokens, temperature,
    cost_per_input_token, cost_per_output_token, currency, priority
) VALUES (
    'WVC', 'werkbon_classification', 'anthropic', 'claude-sonnet-4-20250514', 'Claude Sonnet 4',
    'ANTHROPIC_API_KEY', 1024, 0.0,
    3.00, 15.00, 'EUR', 200  -- Higher priority than default
);
```

---

## Cost Calculation Examples

Based on Anthropic/Mistral pricing (approximate EUR rates):

### Claude Sonnet 4
- Input: €3.00 per 1M tokens
- Output: €15.00 per 1M tokens

### Mistral Large
- Input: €0.80 per 1M tokens
- Output: €2.40 per 1M tokens

### Cost Savings Example

**Scenario:** Classify 1000 werkbonnen/month

**With Claude (current):**
- Avg input: 2500 tokens/request → 2.5M tokens total
- Avg output: 150 tokens/request → 150k tokens total
- Cost: (2.5M × €3.00/1M) + (0.15M × €15.00/1M) = €7.50 + €2.25 = **€9.75/month**

**With Mistral (proposed):**
- Same token counts
- Cost: (2.5M × €0.80/1M) + (0.15M × €2.40/1M) = €2.00 + €0.36 = **€2.36/month**

**Savings: €7.39/month (76% reduction)** for bulk classification

**With Local Mistral (future):**
- Cost: **€0.00** (infrastructure cost only)

---

## Implementation Integration Points

### 1. Configuration Loader Service
**File:** `src/services/llm_config_loader.py` (new)
- Load configuration from Supabase
- Cache in memory with TTL
- Fallback strategy (client-specific → default → hardcoded)

### 2. LLM Provider Abstraction
**File:** `src/services/llm_provider.py` (new)
- Unified interface for all LLM providers
- Handles Anthropic, Mistral, OpenAI, Local APIs
- Automatic token counting
- Usage logging to Supabase

### 3. Modified Services
**Files:**
- `src/services/classifier.py` - Use provider abstraction
- `src/services/contract_generator.py` - Use provider abstraction

### 4. Usage Dashboard
**File:** `pages/30_LLM_Usage.py` (new)
- View token usage by client, action, date
- Cost monitoring and trends
- Model performance comparison

---

## Migration Strategy

### Phase 1: Schema Setup
1. Create Supabase tables
2. Populate default configurations
3. Test connection from application

### Phase 2: Abstraction Layer
1. Build LLM provider abstraction
2. Implement Mistral provider
3. Implement usage logging

### Phase 3: Service Migration
1. Migrate werkbon classification to use abstraction
2. Enable Mistral for classification
3. Monitor quality and performance

### Phase 4: Optimization
1. Deploy local Mistral instance
2. Enable local provider for high-volume clients
3. Cost optimization based on usage data

---

## Supabase Connection Configuration

**Environment Variables:**
```bash
# Add to .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key  # For admin operations
```

**Python Client:**
```python
from supabase import create_client, Client

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)
```

---

## Security Considerations

1. **API Keys:** Never store actual API keys in Supabase; use env var names only
2. **Row Level Security:** Enable RLS on tables if multi-tenant
3. **Service Role:** Use service role key for usage logging (bypasses RLS)
4. **Encryption:** Sensitive metadata in JSONB should be encrypted
5. **Audit:** Track who modifies configurations via `created_by` field

---

## Monitoring & Alerts

### Cost Alerts
- Daily/weekly cost threshold alerts
- Per-client budget monitoring
- Anomaly detection (sudden usage spikes)

### Performance Alerts
- High error rates per provider
- Latency degradation
- Model availability issues

### Implementation
- Supabase Edge Functions for scheduled checks
- Email/Slack notifications
- Dashboard widgets for real-time monitoring

---

## Future Enhancements

1. **A/B Testing:** Compare classification quality across models
2. **Auto-Switching:** Automatically switch to backup provider on errors
3. **Smart Routing:** Use lightweight models for simple cases, heavy models for complex
4. **Prompt Versioning:** Track prompt changes and their impact on usage
5. **Federated Learning:** Train local models on historical classifications

---

## References

- Anthropic API: https://docs.anthropic.com/
- Mistral API: https://docs.mistral.ai/
- Supabase Python Client: https://supabase.com/docs/reference/python
- OpenAI-Compatible Local API: Ollama, vLLM, LocalAI
