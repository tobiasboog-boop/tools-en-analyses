# LLM Configuration System - Migration Guide

## Overview

This guide explains how to integrate the new LLM configuration system into the Contract Check application. The new system enables:

1. **Flexible LLM Provider Selection**: Use different LLMs (Claude, Mistral, local models) for different tasks
2. **Configuration via Supabase**: Centralized configuration management
3. **Usage Tracking**: Automatic logging of token usage and costs
4. **Cost Optimization**: Use cheaper models for bulk work (werkbon classification)

---

## Prerequisites

### 1. Supabase Setup

Create a Supabase project (or use existing "connect notificat app Superbase"):

1. Go to [supabase.com](https://supabase.com)
2. Create project or access existing project
3. Get your project credentials:
   - Project URL: `https://your-project.supabase.co`
   - API Key: Anon/Public key or Service Role key

### 2. Environment Variables

Add to `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-key

# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...  # Existing
MISTRAL_API_KEY=...  # New (optional, for Mistral provider)
OPENAI_API_KEY=...  # New (optional, for OpenAI provider)
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `supabase>=2.3.0` - Supabase Python client
- `openai>=1.12.0` - OpenAI provider support
- `requests>=2.31.0` - HTTP client for Mistral/local APIs

### 4. Create Supabase Tables

Execute the SQL schema in Supabase SQL Editor:

```bash
# Copy contents of sql/llm_supabase_schema.sql
# Paste into Supabase SQL Editor and execute
```

This creates:
- `llm_configurations` table - LLM provider configurations
- `llm_usage_logs` table - Usage tracking
- `llm_usage_summary` view - Aggregated statistics
- Sample configurations for default setup

---

## Migration Steps

### Step 1: Test Supabase Connection

Create a test script to verify connectivity:

```python
# test_supabase.py
import os
from dotenv import load_dotenv
from src.services.llm_config_service import get_llm_config_service

load_dotenv()

try:
    service = get_llm_config_service()
    configs = service.list_configurations()
    print(f"✓ Supabase connected! Found {len(configs)} configurations")
    for config in configs:
        print(f"  - {config['action_type']}: {config['provider']} ({config['model_name']})")
except Exception as e:
    print(f"✗ Supabase connection failed: {e}")
```

Run:
```bash
python test_supabase.py
```

Expected output:
```
✓ Supabase connected! Found 3 configurations
  - contract_generation: anthropic (claude-sonnet-4-20250514)
  - werkbon_classification: mistral (mistral-large-latest)
  - werkbon_classification: local (mistral-7b-instruct)
```

---

### Step 2: Migrate Classifier Service

#### Current Code (classifier.py)

```python
from anthropic import Anthropic

class ClassificationService:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def classify_werkbon(self, werkbon, contract_text, client_config):
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        # Parse response...
```

#### Migrated Code (classifier.py)

```python
from src.services.llm_service import get_llm_service

class ClassificationService:
    def __init__(self, enable_supabase=True):
        self.llm_service = get_llm_service(
            enable_supabase=enable_supabase,
            enable_usage_logging=enable_supabase
        )

    def classify_werkbon(self, werkbon, contract_text, client_config):
        # Build prompts (unchanged)
        system_prompt = self._build_system_prompt(client_config)
        user_message = self._build_user_message(werkbon, contract_text)

        # Call LLM service (replaces client.messages.create)
        response = self.llm_service.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            action_type="werkbon_classification",
            client_id=werkbon.debiteur_code,  # Or appropriate client ID
            werkbon_id=str(werkbon.id),
            max_tokens=1024,
            temperature=0.0
        )

        # Check for errors
        if not response.success:
            raise Exception(f"LLM error: {response.error_message}")

        # Parse response (unchanged logic)
        return self._parse_response(response.content)
```

**Key Changes:**
1. Replace `Anthropic` client with `LLMService`
2. Use `llm_service.generate()` instead of `client.messages.create()`
3. Add `action_type`, `client_id`, `werkbon_id` for tracking
4. Response format: `response.content` contains the text
5. Automatic usage logging happens in background

**Benefits:**
- Automatically uses Mistral (cheaper) instead of Claude
- Usage tracked in Supabase
- Can switch models via Supabase without code changes

---

### Step 3: Migrate Contract Generator Service

#### Current Code (contract_generator.py)

```python
from anthropic import Anthropic

class ContractLLMGenerator:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def generate_llm_ready_contract(self, contract_id):
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        # Process response...
```

#### Migrated Code (contract_generator.py)

```python
from src.services.llm_service import get_llm_service

class ContractLLMGenerator:
    def __init__(self, enable_supabase=True):
        self.llm_service = get_llm_service(
            enable_supabase=enable_supabase,
            enable_usage_logging=enable_supabase
        )

    def generate_llm_ready_contract(self, contract_id):
        # Build prompts (unchanged)
        system_prompt = SYSTEM_PROMPT
        user_message = self._build_user_message(contract)

        # Call LLM service
        response = self.llm_service.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            action_type="contract_generation",
            client_id=contract.debiteur_code,  # Or appropriate client ID
            contract_id=str(contract_id),
            max_tokens=4096,
            temperature=0.0
        )

        # Check for errors
        if not response.success:
            raise Exception(f"LLM error: {response.error_message}")

        # Process response (unchanged logic)
        return response.content
```

**Benefits:**
- Keeps using Claude (configured for this action)
- Usage tracked automatically
- Can be monitored for cost optimization

---

### Step 4: Backward Compatibility (Optional)

For gradual migration, support both systems:

```python
class ClassificationService:
    def __init__(self, use_new_llm_system=True):
        self.use_new_llm_system = use_new_llm_system

        if use_new_llm_system:
            try:
                self.llm_service = get_llm_service()
                print("Using new LLM configuration system")
            except Exception as e:
                print(f"Falling back to old system: {e}")
                self.use_new_llm_system = False
                self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def classify_werkbon(self, werkbon, contract_text, client_config):
        if self.use_new_llm_system:
            return self._classify_new(werkbon, contract_text, client_config)
        else:
            return self._classify_old(werkbon, contract_text, client_config)
```

---

## Configuration Management

### View Current Configurations

```python
from src.services.llm_config_service import get_llm_config_service

service = get_llm_config_service()
configs = service.list_configurations()

for config in configs:
    print(f"{config['action_type']} -> {config['provider']} ({config['model_name']})")
    print(f"  Active: {config['is_active']}, Priority: {config['priority']}")
    print(f"  Cost: €{config['cost_per_input_token']}/1M input, €{config['cost_per_output_token']}/1M output")
```

### Add Client-Specific Override

Example: WVC uses Claude for everything (premium client)

```python
service.create_configuration({
    "client_id": "WVC",
    "action_type": "werkbon_classification",
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514",
    "model_alias": "Claude Sonnet 4",
    "api_key_env_var": "ANTHROPIC_API_KEY",
    "max_tokens": 1024,
    "temperature": 0.0,
    "cost_per_input_token": 3.00,
    "cost_per_output_token": 15.00,
    "currency": "EUR",
    "priority": 200,  # Higher than default (100)
    "notes": "Premium client uses Claude for all operations"
})
```

### Switch to Local Mistral (Zero Cost)

When local Mistral server is deployed:

```python
# Activate local configuration
service.update_configuration(
    config_id="<uuid-of-local-config>",
    updates={"is_active": True, "priority": 150}
)

# Or create new local config
service.create_configuration({
    "client_id": None,  # Default for all
    "action_type": "werkbon_classification",
    "provider": "local",
    "model_name": "mistral-7b-instruct",
    "api_endpoint": "http://your-server:11434/v1/chat/completions",
    "max_tokens": 1024,
    "temperature": 0.0,
    "cost_per_input_token": 0.0,
    "cost_per_output_token": 0.0,
    "priority": 150,  # Higher than Mistral API (100)
    "is_active": True
})
```

---

## Usage Tracking & Analytics

### Get Usage Statistics

```python
from src.services.llm_usage_logger import get_llm_usage_logger
from datetime import datetime, timedelta

logger = get_llm_usage_logger()

# Last 30 days
start_date = datetime.now() - timedelta(days=30)
stats = logger.get_usage_stats(start_date=start_date)

print(f"Total Requests: {stats['total_requests']}")
print(f"Total Tokens: {stats['total_tokens']:,}")
print(f"Total Cost: €{stats['total_cost']:.2f}")
print(f"Avg Cost/Request: €{stats['avg_cost_per_request']:.4f}")
print(f"Success Rate: {stats['success_rate']*100:.1f}%")
```

### Breakdown by Action

```python
breakdown = logger.get_usage_by_action(start_date=start_date)

for action, stats in breakdown.items():
    print(f"\n{action}:")
    print(f"  Requests: {stats['request_count']}")
    print(f"  Tokens: {stats['total_tokens']:,}")
    print(f"  Cost: €{stats['total_cost']:.2f}")
    print(f"  Avg Latency: {stats['avg_latency_ms']}ms")
```

### Monitor Recent Errors

```python
errors = logger.get_recent_errors(limit=10)

for error in errors:
    print(f"Error at {error['created_at']}:")
    print(f"  Action: {error['action_type']}")
    print(f"  Provider: {error['provider']} ({error['model_name']})")
    print(f"  Message: {error['error_message']}")
```

---

## Testing Different Providers

### Test Mistral vs Claude

```python
from src.services.llm_service import get_llm_service

llm = get_llm_service()

# Test with default config (will use Mistral for classification)
response1 = llm.generate(
    system_prompt="You are a contract analyzer.",
    user_message="Is this werkbon in contract scope?",
    action_type="werkbon_classification"
)

print(f"Provider: {response1.provider}, Model: {response1.model}")
print(f"Cost: €{response1.usage.total_cost:.6f}")

# Test with contract generation (will use Claude)
response2 = llm.generate(
    system_prompt="Transform this contract.",
    user_message="Contract text here...",
    action_type="contract_generation"
)

print(f"Provider: {response2.provider}, Model: {response2.model}")
print(f"Cost: €{response2.usage.total_cost:.6f}")
```

### A/B Test Quality

Compare classification quality between providers:

```python
# Test same werkbon with both providers
test_cases = [...]  # List of test werkbonnen

# Test with Mistral (default)
mistral_results = []
for werkbon in test_cases:
    result = classify_werkbon(werkbon, use_provider="mistral")
    mistral_results.append(result)

# Test with Claude (override)
claude_results = []
for werkbon in test_cases:
    result = classify_werkbon(werkbon, use_provider="anthropic")
    claude_results.append(result)

# Compare accuracy
mistral_accuracy = calculate_accuracy(mistral_results)
claude_accuracy = calculate_accuracy(claude_results)

print(f"Mistral: {mistral_accuracy:.1%} accuracy, €{mistral_cost:.2f} total")
print(f"Claude: {claude_accuracy:.1%} accuracy, €{claude_cost:.2f} total")
```

---

## Rollout Strategy

### Phase 1: Setup (Week 1)
1. ✅ Create Supabase tables
2. ✅ Add environment variables
3. ✅ Install dependencies
4. ✅ Test connection

### Phase 2: Parallel Testing (Week 2)
1. Run both old and new systems in parallel
2. Log results from both
3. Compare quality and costs
4. Fine-tune configurations

### Phase 3: Gradual Migration (Week 3)
1. Migrate contract generation first (low volume)
2. Monitor for issues
3. Migrate werkbon classification (high volume)
4. Monitor cost savings

### Phase 4: Optimization (Week 4)
1. Deploy local Mistral server
2. Enable local provider for bulk work
3. Monitor zero-cost classification
4. Keep Claude for premium clients

---

## Monitoring Dashboard (Future)

Create Streamlit page for monitoring:

**File:** `pages/30_LLM_Usage.py`

```python
import streamlit as st
from src.services.llm_usage_logger import get_llm_usage_logger
from datetime import datetime, timedelta

st.title("LLM Usage & Costs")

# Date range selector
col1, col2 = st.columns(2)
start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
end_date = col2.date_input("End Date", datetime.now())

# Get statistics
logger = get_llm_usage_logger()
stats = logger.get_usage_stats(
    start_date=datetime.combine(start_date, datetime.min.time()),
    end_date=datetime.combine(end_date, datetime.max.time())
)

# Display metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Requests", f"{stats['total_requests']:,}")
col2.metric("Total Tokens", f"{stats['total_tokens']:,}")
col3.metric("Total Cost", f"€{stats['total_cost']:.2f}")
col4.metric("Success Rate", f"{stats['success_rate']*100:.1f}%")

# Breakdown by action
st.subheader("Usage by Action")
breakdown = logger.get_usage_by_action(
    start_date=datetime.combine(start_date, datetime.min.time()),
    end_date=datetime.combine(end_date, datetime.max.time())
)

import pandas as pd
df = pd.DataFrame(breakdown).T
st.dataframe(df)
```

---

## Cost Savings Example

**Current System (Claude for everything):**
- 1000 werkbon classifications/month
- Avg 2500 input tokens, 150 output tokens
- Cost: (2.5M × €3/1M) + (0.15M × €15/1M) = **€9.75/month**

**New System (Mistral for classification):**
- Same token counts
- Cost: (2.5M × €0.80/1M) + (0.15M × €2.40/1M) = **€2.36/month**
- **Savings: €7.39/month (76% reduction)**

**Future (Local Mistral):**
- Cost: **€0.00** (infrastructure cost only)
- **Savings: 100% on LLM API costs**

---

## Troubleshooting

### Issue: Supabase connection fails

**Solution:**
```python
# Check environment variables
import os
print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SUPABASE_KEY:", os.getenv("SUPABASE_KEY")[:20] + "...")

# Test direct connection
from supabase import create_client
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
result = client.table("llm_configurations").select("*").limit(1).execute()
print("Configurations found:", len(result.data))
```

### Issue: No configurations found

**Solution:**
```sql
-- Re-run sample data insertion from llm_supabase_schema.sql
-- Or add manually in Supabase dashboard
```

### Issue: Usage not logging

**Solution:**
```python
# Test logger directly
from src.services.llm_usage_logger import get_llm_usage_logger
from src.services.llm_provider import LLMResponse, LLMUsageMetrics

logger = get_llm_usage_logger()
test_response = LLMResponse(
    content="Test",
    usage=LLMUsageMetrics(input_tokens=100, output_tokens=50),
    provider="test",
    model="test-model"
)

log_id = logger.log_usage(
    response=test_response,
    action_type="test"
)

print("Log ID:", log_id)  # Should print UUID if successful
```

---

## Support

For issues or questions:
1. Check logs: `journalctl -u contract-checker-pilot -f`
2. Review Supabase logs in dashboard
3. Test individual components with scripts above
4. Contact development team

---

## Next Steps

1. ✅ Complete this migration guide
2. ⬜ Test Supabase connection on VPS4
3. ⬜ Migrate classifier.py
4. ⬜ Migrate contract_generator.py
5. ⬜ Monitor usage for 1 week
6. ⬜ Deploy local Mistral server
7. ⬜ Create usage dashboard page
