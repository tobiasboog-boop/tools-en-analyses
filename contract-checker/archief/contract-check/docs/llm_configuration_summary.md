# LLM Configuration System - Implementation Summary

## Overview

A complete LLM abstraction and configuration system has been implemented for the Contract Check application. This system enables flexible provider selection, cost optimization, and comprehensive usage tracking via Supabase.

**Branch:** `feature/llm-configuration`

**Status:** ✅ Implementation Complete - Ready for Testing

---

## Goals Achieved

### 1. LLM Provider Abstraction ✅
- Unified interface supporting multiple providers:
  - **Anthropic** (Claude) - Current provider
  - **Mistral** - Cost-effective alternative
  - **OpenAI** - GPT models support
  - **Local** - Self-hosted models (Ollama, vLLM, etc.)

### 2. Configuration via Supabase ✅
- Centralized configuration management
- Per-client and per-action customization
- Priority-based provider selection
- Dynamic configuration without code changes

### 3. Usage Tracking & Cost Monitoring ✅
- Automatic logging of all LLM API calls
- Token usage tracking (input/output)
- Cost calculation per request
- Performance metrics (latency, success rate)
- Aggregated statistics and reporting

### 4. Cost Optimization Strategy ✅
- **Heavy LLMs (Claude)** for contract processing (complex, low volume)
- **Lighter LLMs (Mistral/local)** for werkbon classification (simpler, high volume)
- Projected savings: **76% cost reduction** on bulk classification
- Future: **100% savings** with local model deployment

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                      │
│  (classifier.py, contract_generator.py, Streamlit UI)  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   LLM Service                           │
│  (Unified interface with usage logging)                 │
└──────────────────────┬──────────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐
│  Config Service      │  │  Usage Logger        │
│  (Supabase)          │  │  (Supabase)          │
└──────────┬───────────┘  └──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│              Provider Abstraction Layer                 │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │Anthropic │  │ Mistral  │  │ OpenAI   │  │ Local  │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Files Created

#### Core Abstraction Layer
```
src/services/llm_provider/
├── __init__.py                  # Package exports
├── base.py                      # Base classes (LLMProvider, LLMRequest, LLMResponse)
├── anthropic_provider.py        # Claude API implementation
├── mistral_provider.py          # Mistral API implementation
├── openai_provider.py           # OpenAI API implementation
├── local_provider.py            # Local model API implementation
└── factory.py                   # Provider factory
```

#### Services
```
src/services/
├── llm_config_service.py        # Supabase configuration management
├── llm_usage_logger.py          # Usage tracking and analytics
├── llm_service.py               # Unified high-level service
└── classifier_new.py            # Example migrated classifier
```

#### Documentation
```
docs/
├── llm_supabase_schema.md       # Schema design and rationale
├── llm_migration_guide.md       # Step-by-step migration guide
└── llm_configuration_summary.md # This file
```

#### Database Schema
```
sql/
└── llm_supabase_schema.sql      # Supabase table creation script
```

---

## Database Schema

### Tables

#### 1. `llm_configurations`
Stores LLM provider configurations for different clients and action types.

**Key Fields:**
- `client_id` - NULL for default, specific for client overrides
- `action_type` - 'contract_generation', 'werkbon_classification', etc.
- `provider` - 'anthropic', 'mistral', 'openai', 'local'
- `model_name` - Specific model identifier
- `cost_per_input_token` / `cost_per_output_token` - Per 1M tokens
- `priority` - Higher priority preferred when multiple matches
- `is_active` - Enable/disable configuration

**Lookup Strategy:**
1. Check for `client_id` + `action_type` match (highest priority)
2. Fallback to `NULL` + `action_type` (default)
3. Use `priority` to select when multiple active configs exist

#### 2. `llm_usage_logs`
Tracks every LLM API call with comprehensive metrics.

**Key Fields:**
- `config_id` - Reference to configuration used
- `action_type`, `client_id`, `werkbon_id`, `contract_id` - Context
- `provider`, `model_name` - Which model was used
- `input_tokens`, `output_tokens`, `total_tokens` - Token usage
- `input_cost`, `output_cost`, `total_cost` - Calculated costs
- `latency_ms` - Response time
- `success` / `error_message` - Status
- `metadata` - Additional contextual data (JSONB)

#### 3. `llm_usage_summary` (Materialized View)
Pre-aggregated daily statistics for reporting.

---

## Configuration Examples

### Default Configuration

```sql
-- Contract Generation: Claude (heavy lifting)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name,
    cost_per_input_token, cost_per_output_token, priority
) VALUES (
    NULL, 'contract_generation', 'anthropic', 'claude-sonnet-4-20250514',
    3.00, 15.00, 100
);

-- Werkbon Classification: Mistral (bulk work, cost-effective)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name,
    cost_per_input_token, cost_per_output_token, priority
) VALUES (
    NULL, 'werkbon_classification', 'mistral', 'mistral-large-latest',
    0.80, 2.40, 100
);
```

### Client-Specific Override

```sql
-- WVC uses Claude for everything (premium client)
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name,
    cost_per_input_token, cost_per_output_token, priority
) VALUES (
    'WVC', 'werkbon_classification', 'anthropic', 'claude-sonnet-4-20250514',
    3.00, 15.00, 200  -- Higher priority than default
);
```

### Local Model (Zero Cost)

```sql
-- Local Mistral for bulk processing
INSERT INTO llm_configurations (
    client_id, action_type, provider, model_name, api_endpoint,
    cost_per_input_token, cost_per_output_token, priority, is_active
) VALUES (
    NULL, 'werkbon_classification', 'local', 'mistral-7b-instruct',
    'http://localhost:11434/v1/chat/completions',
    0.00, 0.00, 150, true
);
```

---

## Usage Examples

### Basic Classification

```python
from src.services.llm_service import get_llm_service

# Initialize service (uses Supabase config)
llm = get_llm_service()

# Classify werkbon (automatically uses Mistral based on config)
response = llm.generate(
    system_prompt="You are a contract analyzer...",
    user_message="Analyze this werkbon against contract...",
    action_type="werkbon_classification",
    client_id="WVC",
    werkbon_id="12345"
)

print(f"Used: {response.provider} ({response.model})")
print(f"Cost: €{response.usage.total_cost:.6f}")
print(f"Result: {response.content}")
```

### Get Provider Info

```python
# Check which provider will be used
info = llm.get_provider_info(
    action_type="werkbon_classification",
    client_id="WVC"
)

print(f"Provider: {info['provider']}")
print(f"Model: {info['model']}")
print(f"Cost: €{info['cost_per_input_token']}/1M input")
```

### Usage Statistics

```python
from src.services.llm_usage_logger import get_llm_usage_logger
from datetime import datetime, timedelta

logger = get_llm_usage_logger()

# Last 30 days
stats = logger.get_usage_stats(
    start_date=datetime.now() - timedelta(days=30)
)

print(f"Total Requests: {stats['total_requests']}")
print(f"Total Cost: €{stats['total_cost']:.2f}")
print(f"Success Rate: {stats['success_rate']*100:.1f}%")

# Breakdown by action
breakdown = logger.get_usage_by_action()
for action, data in breakdown.items():
    print(f"{action}: {data['request_count']} requests, €{data['total_cost']:.2f}")
```

---

## Migration Path

### Phase 1: Setup ✅ (Completed)
- [x] Create Supabase schema
- [x] Implement provider abstraction
- [x] Build configuration service
- [x] Create usage logger
- [x] Write documentation

### Phase 2: Testing (Next Steps)
- [ ] Add Supabase credentials to `.env`
- [ ] Execute SQL schema in Supabase
- [ ] Test configuration loading
- [ ] Test different providers
- [ ] Verify usage logging

### Phase 3: Integration
- [ ] Update `classifier.py` to use new system
- [ ] Update `contract_generator.py` to use new system
- [ ] Add backward compatibility flags
- [ ] Run parallel testing (old vs new)

### Phase 4: Deployment
- [ ] Deploy to VPS4
- [ ] Monitor usage and costs
- [ ] Compare quality metrics
- [ ] Fine-tune configurations

### Phase 5: Optimization
- [ ] Deploy local Mistral server
- [ ] Enable zero-cost classification
- [ ] Create usage dashboard
- [ ] Set up cost alerts

---

## Cost Analysis

### Current System (Claude for everything)

**Werkbon Classification (1000/month):**
- Avg tokens: 2500 input, 150 output
- Cost: (2.5M × €3/1M) + (0.15M × €15/1M) = **€9.75/month**

**Contract Generation (50/month):**
- Avg tokens: 3000 input, 2000 output
- Cost: (0.15M × €3/1M) + (0.1M × €15/1M) = **€1.95/month**

**Total: €11.70/month**

### New System (Optimized)

**Werkbon Classification with Mistral (1000/month):**
- Same token counts
- Cost: (2.5M × €0.80/1M) + (0.15M × €2.40/1M) = **€2.36/month**
- Savings: **€7.39/month (76% reduction)**

**Contract Generation with Claude (50/month):**
- Same as before: **€1.95/month**

**Total: €4.31/month**
**Monthly Savings: €7.39 (63% reduction)**
**Annual Savings: €88.68**

### Future System (Local Mistral)

**Werkbon Classification with Local Model (1000/month):**
- Cost: **€0.00** (infrastructure cost only)

**Contract Generation with Claude (50/month):**
- Still: **€1.95/month**

**Total: €1.95/month**
**Monthly Savings: €9.75 (83% reduction)**
**Annual Savings: €117.00**

---

## Testing Checklist

### Environment Setup
- [ ] Add `SUPABASE_URL` to `.env`
- [ ] Add `SUPABASE_KEY` to `.env`
- [ ] Add `MISTRAL_API_KEY` to `.env` (optional)
- [ ] Install dependencies: `pip install -r requirements.txt`

### Database Setup
- [ ] Execute `sql/llm_supabase_schema.sql` in Supabase
- [ ] Verify tables created: `llm_configurations`, `llm_usage_logs`, `llm_usage_summary`
- [ ] Check sample configurations inserted

### Connection Testing
- [ ] Test Supabase connection
- [ ] Load configurations from database
- [ ] Test each provider:
  - [ ] Anthropic (existing)
  - [ ] Mistral (if API key available)
  - [ ] Local (if server running)

### Integration Testing
- [ ] Test `LLMService.generate()` with different action types
- [ ] Verify provider selection logic
- [ ] Check usage logging to Supabase
- [ ] Validate cost calculations

### Migration Testing
- [ ] Test `classifier_new.py` with sample werkbon
- [ ] Compare results with current classifier
- [ ] Measure performance and costs
- [ ] Verify database persistence

---

## Configuration Management

### View Configurations

```python
from src.services.llm_config_service import get_llm_config_service

service = get_llm_config_service()
configs = service.list_configurations()

for config in configs:
    print(f"{config['action_type']} -> {config['provider']} ({config['model_name']})")
    print(f"  Priority: {config['priority']}, Active: {config['is_active']}")
```

### Add Configuration

```python
service.create_configuration({
    "client_id": "CLIENT123",
    "action_type": "werkbon_classification",
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514",
    "api_key_env_var": "ANTHROPIC_API_KEY",
    "max_tokens": 1024,
    "temperature": 0.0,
    "cost_per_input_token": 3.00,
    "cost_per_output_token": 15.00,
    "priority": 200,
    "notes": "Premium client override"
})
```

### Update Configuration

```python
service.update_configuration(
    config_id="<uuid>",
    updates={"is_active": False, "notes": "Temporarily disabled"}
)
```

### Clear Cache

```python
# Clear all cached configurations
service.clear_cache()

# Clear specific client
service.clear_cache(client_id="WVC")

# Clear specific action
service.clear_cache(action_type="werkbon_classification")
```

---

## Monitoring & Analytics

### Usage Dashboard (Future)

Create Streamlit page: `pages/30_LLM_Usage.py`

**Features:**
- Real-time usage metrics
- Cost tracking by client/action
- Provider performance comparison
- Error monitoring
- Token usage trends
- Cost alerts

### Key Metrics

1. **Cost Metrics**
   - Total cost per day/week/month
   - Cost per action type
   - Cost per client
   - Average cost per request

2. **Performance Metrics**
   - Average latency by provider
   - Success rate
   - Error frequency and patterns
   - Token efficiency

3. **Usage Patterns**
   - Requests per provider
   - Requests per action type
   - Peak usage times
   - Client distribution

---

## Deployment Notes

### Environment Variables Required

```bash
# Existing
ANTHROPIC_API_KEY=sk-ant-...
DB_HOST=localhost
DB_PORT=5432
# ... other DB vars ...

# New (Required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# New (Optional - for alternative providers)
MISTRAL_API_KEY=...
OPENAI_API_KEY=...
```

### Deployment to VPS4

```bash
# 1. Update code
git push origin feature/llm-configuration

# 2. SSH to server
ssh -i ~/.ssh/id_rsa user@vps4-host

# 3. Pull changes
cd /opt/notifica/contract-checker
git checkout feature/llm-configuration
git pull

# 4. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 5. Add Supabase credentials to .env
nano .env
# Add SUPABASE_URL and SUPABASE_KEY

# 6. Restart service
sudo systemctl restart contract-checker-pilot

# 7. Monitor logs
journalctl -u contract-checker-pilot -f
```

---

## Troubleshooting

### Issue: Supabase connection fails

**Check:**
```python
import os
print(os.getenv("SUPABASE_URL"))
print(os.getenv("SUPABASE_KEY")[:20] + "...")
```

**Test connection:**
```python
from supabase import create_client
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
result = client.table("llm_configurations").select("*").limit(1).execute()
print(f"Configurations: {len(result.data)}")
```

### Issue: No configurations found

**Solution:** Re-execute sample data insertion from `sql/llm_supabase_schema.sql`

### Issue: Provider not working

**Check:**
- API key environment variable set correctly
- Provider-specific dependencies installed
- API endpoint accessible (for local/custom endpoints)

**Test provider directly:**
```python
from src.services.llm_provider import LLMProviderFactory, LLMRequest

provider = LLMProviderFactory.create_provider(
    provider="mistral",
    model="mistral-large-latest"
)

request = LLMRequest(
    system_prompt="Test",
    user_message="Hello",
    action_type="test"
)

response = provider.generate(request)
print(response.content)
```

---

## Next Steps

1. **Immediate:**
   - Add Supabase credentials to development environment
   - Test connection and configuration loading
   - Run sample classifications with different providers

2. **Short-term:**
   - Migrate `classifier.py` to new system
   - Parallel testing (old vs new)
   - Monitor quality and costs

3. **Medium-term:**
   - Deploy to production
   - Create usage dashboard
   - Set up cost monitoring alerts

4. **Long-term:**
   - Deploy local Mistral server
   - Enable zero-cost bulk classification
   - Expand to other LLM use cases

---

## Success Criteria

✅ **Implementation Complete:**
- [x] LLM provider abstraction layer
- [x] Supabase configuration management
- [x] Usage tracking and logging
- [x] Multiple provider support
- [x] Cost calculation
- [x] Comprehensive documentation

⏳ **Pending Testing:**
- [ ] Supabase connection verified
- [ ] All providers tested
- [ ] Usage logging confirmed
- [ ] Cost tracking validated

⏳ **Pending Integration:**
- [ ] Services migrated
- [ ] Quality validated
- [ ] Cost savings confirmed
- [ ] Dashboard created

---

## Resources

- **Schema Design:** `docs/llm_supabase_schema.md`
- **Migration Guide:** `docs/llm_migration_guide.md`
- **SQL Schema:** `sql/llm_supabase_schema.sql`
- **Example Migration:** `src/services/classifier_new.py`
- **Supabase Docs:** https://supabase.com/docs
- **Anthropic API:** https://docs.anthropic.com/
- **Mistral API:** https://docs.mistral.ai/

---

## Contact

For questions or issues during testing/migration:
- Review documentation in `docs/` folder
- Check implementation examples in `src/services/`
- Test individual components with provided scripts
- Consult Supabase logs for debugging

**Ready for Testing! 🚀**
