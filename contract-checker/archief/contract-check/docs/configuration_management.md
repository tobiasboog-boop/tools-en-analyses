# Configuration Management - Overzicht

## 📋 Configuratie Locaties

### 1. `.env` File (Local Development & VPS Deployment)

**Locatie:** `c:\Projects\contract-check\.env`

**Wat:** Gevoelige credentials en environment-specifieke settings

```bash
# ============================================================================
# SUPABASE (Centrale Database)
# ============================================================================
SUPABASE_URL=https://usxstdmeljiclmcbjgvu.supabase.co
SUPABASE_ANON_KEY=eyJ...              # Voor client-side queries
SUPABASE_SERVICE_KEY=eyJ...           # Voor backend operations (RLS bypass)

# ============================================================================
# LLM PROVIDER API KEYS
# ============================================================================
ANTHROPIC_API_KEY=sk-ant-...          # Claude API
MISTRAL_API_KEY=                      # Mistral AI (optioneel)
OPENAI_API_KEY=                       # OpenAI (optioneel)

# ============================================================================
# DATABASE (Legacy PostgreSQL)
# ============================================================================
DB_HOST=10.3.152.9
DB_PORT=5432
DB_NAME=1210
DB_USER=postgres
DB_PASSWORD=...
DB_SCHEMA=contract_checker

# ============================================================================
# APP SETTINGS (kunnen naar Supabase)
# ============================================================================
CONFIDENCE_THRESHOLD=0.85             # → Kan naar app_configuration tabel
CONTRACTS_FOLDER=C:/...               # Environment-specifiek, blijft in .env

# ============================================================================
# VPS4 SSH (voor deployment)
# ============================================================================
VPS4_HOST=212.132.90.158
VPS4_USER=root
VPS4_SSH_KEY_PATH=C:/...
VPS4_SSH_PASSPHRASE=...
```

**Wanneer Gebruiken:**
- ✅ API keys (NOOIT committen!)
- ✅ Database credentials
- ✅ Environment-specifieke paden
- ✅ Secrets en passwords

**Wanneer NIET Gebruiken:**
- ❌ Business logic configuratie (→ Supabase)
- ❌ Feature flags (→ Supabase)
- ❌ User-editable settings (→ Supabase)

---

### 2. Supabase `llm_providers` & `llm_models` Tabellen

**Wat:** LLM provider informatie en pricing

**Voorbeeld:**
```sql
-- Provider info
SELECT * FROM llm_providers;

code       | name                | api_endpoint
-----------|---------------------|------------------
anthropic  | Anthropic (Claude)  | https://api.anthropic.com/v1/messages
mistral    | Mistral AI          | https://api.mistral.ai/v1/chat/completions
openai     | OpenAI              | https://api.openai.com/v1/chat/completions
local      | Local/Self-Hosted   | http://localhost:11434/v1/chat/completions

-- Model pricing
SELECT * FROM llm_models;

model_name           | cost_per_input | cost_per_output | is_recommended
---------------------|----------------|-----------------|----------------
Claude Sonnet 4      | 3.00           | 15.00           | true
Mistral Large        | 0.80           | 2.40            | true
```

**Wanneer Gebruiken:**
- ✅ Provider metadata (namen, URLs)
- ✅ Model pricing (per 1M tokens)
- ✅ Model capabilities (max tokens, vision support)

**Wanneer NIET Gebruiken:**
- ❌ API keys (→ .env)
- ❌ Welk model voor welke klant (→ llm_configurations)

---

### 3. Supabase `llm_configurations` Tabel

**Wat:** Welk LLM model gebruiken voor welke app/klant/actie

**Voorbeeld:**
```sql
-- Default: Alle klanten gebruiken Mistral voor classificatie
SELECT * FROM llm_configurations_overview
WHERE app_code = 'werkbon-checker';

app_name                  | organization | action_type          | model_name    | priority
--------------------------|--------------|----------------------|---------------|----------
Werkbon Contract Checker  | NULL (all)   | contract_generation  | Claude Sonnet | 100
Werkbon Contract Checker  | NULL (all)   | werkbon_classification | Mistral Large | 100

-- Override: WVC gebruikt Claude voor alles
INSERT INTO llm_configurations (...)
VALUES (werkbon_checker_id, wvc_org_id, 'werkbon_classification', claude_id, ..., 200);
```

**Wanneer Gebruiken:**
- ✅ Per-app LLM selectie
- ✅ Per-klant overrides (WVC = premium)
- ✅ Per-action type configuratie
- ✅ Model parameters (temperature, max_tokens)

---

### 4. Supabase `app_configuration` Tabel (Nieuw!)

**Wat:** App-wide business settings die editeerbaar zijn via admin UI

**Voorbeeld:**
```sql
SELECT * FROM app_configuration_overview
WHERE app_code = 'werkbon-checker';

config_key                    | value  | type    | description
------------------------------|--------|---------|----------------------------------
confidence_threshold          | 0.85   | number  | Min score voor classificatie
max_batch_size                | 100    | number  | Max werkbonnen per batch
enable_llm_caching            | true   | boolean | LLM ready contracts cachen
feature_quick_classification  | true   | boolean | Quick Classificatie enabled
ui_items_per_page             | 50     | number  | Items per pagina in tabellen
ui_theme_primary_color        | #667eea| string  | Primary theme color
```

**Wanneer Gebruiken:**
- ✅ Business logic parameters (confidence threshold)
- ✅ Feature flags (enable/disable features)
- ✅ UI settings (items per page, colors)
- ✅ Timeouts en limits
- ✅ Alles wat een admin moet kunnen aanpassen

**Wanneer NIET Gebruiken:**
- ❌ API keys (→ .env)
- ❌ Environment-specifieke paden (→ .env)
- ❌ LLM model pricing (→ llm_models)

---

## 🔄 Migratie Strategie

### Van .env naar Supabase

**Voorheen in .env:**
```bash
CONFIDENCE_THRESHOLD=0.85
MAX_BATCH_SIZE=100
```

**Nu in Supabase:**
```sql
-- app_configuration tabel
config_key             | config_value
-----------------------|-------------
confidence_threshold   | 0.85
max_batch_size         | 100
```

**Python Code Update:**
```python
# Oud (hardcoded)
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))

# Nieuw (Supabase)
from src.services.config_service import get_app_config

confidence_threshold = get_app_config("werkbon-checker", "confidence_threshold")
# Returns: 0.85 (float parsed from string)
```

---

## 📊 Decision Matrix

| Setting Type | .env | Supabase app_config | Supabase llm_* | Hardcoded |
|--------------|------|---------------------|----------------|-----------|
| API Keys | ✅ | ❌ | ❌ | ❌ |
| DB Credentials | ✅ | ❌ | ❌ | ❌ |
| File Paths | ✅ | ❌ | ❌ | ❌ |
| SSH Keys | ✅ | ❌ | ❌ | ❌ |
| Confidence Threshold | ❌ | ✅ | ❌ | ❌ |
| Feature Flags | ❌ | ✅ | ❌ | ❌ |
| UI Settings | ❌ | ✅ | ❌ | ❌ |
| LLM Pricing | ❌ | ❌ | ✅ | ❌ |
| LLM Model Selection | ❌ | ❌ | ✅ | ❌ |
| App Version | ❌ | ❌ | ❌ | ✅ |
| Python Imports | ❌ | ❌ | ❌ | ✅ |

---

## 🔐 Security Best Practices

### .env File
```bash
# ✅ GOOD
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_SERVICE_KEY=eyJ...

# ❌ NEVER commit .env to git!
# .gitignore moet bevatten:
.env
.env.local
.env.production
```

### Supabase Tables
```sql
-- ✅ GOOD: API key env var naam opslaan
INSERT INTO llm_providers (api_key_env_var) VALUES ('ANTHROPIC_API_KEY');

-- ❌ NEVER: Echte API key in database
INSERT INTO llm_providers (api_key) VALUES ('sk-ant-...');
```

---

## 🚀 Deployment Checklist

### VPS4 Deployment

**1. Update .env op server:**
```bash
ssh vps4
cd /opt/notifica/contract-checker
nano .env

# Add/update:
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
MISTRAL_API_KEY=...
```

**2. Deploy app_configuration schema (eenmalig):**
```bash
# In Supabase SQL Editor:
# Run: sql/003_app_configuration.sql
```

**3. Restart service:**
```bash
sudo systemctl restart contract-checker-pilot
journalctl -u contract-checker-pilot -f
```

---

## 📝 Usage Examples

### Python: Lees Config (Method 1 - Recommended)

```python
from src.services.config_service import get_app_config

# Get global config (automatically parsed to correct type)
threshold = get_app_config('confidence_threshold', default=0.85)
# Returns: 0.85 (float) - automatically parsed from string

# Get org-specific config (met fallback naar global)
threshold_wvc = get_app_config(
    'confidence_threshold',
    organization_id=wvc_org_id,
    default=0.85
)
# Returns org-specific value if exists, else global, else default

# Check feature flag (automatically parsed to bool)
if get_app_config('feature_quick_classification', default=True):
    # Feature enabled
    pass

# Get batch size (automatically parsed to int)
batch_size = get_app_config('max_batch_size', default=100)
```

### Python: Lees Config (Method 2 - Config Service)

```python
from src.services.config_service import get_config_service

# Get config service instance
config_service = get_config_service('werkbon-checker')

# Read individual configs
threshold = config_service.get_config('confidence_threshold', default=0.85)
batch_size = config_service.get_config('max_batch_size', default=100)

# Read all configs at once (efficient for multiple configs)
all_configs = config_service.get_all_configs()
# Returns: {'confidence_threshold': 0.85, 'max_batch_size': 100, ...}
```

### Python: Direct SQL Function (Advanced)

```python
# Only use if you need raw SQL access
from supabase import create_client

client = create_client(supabase_url, supabase_key)

result = client.rpc('get_app_config', {
    'p_app_code': 'werkbon-checker',
    'p_config_key': 'confidence_threshold'
}).execute()

# Returns: '0.85' (string) - you need to parse manually
threshold = float(result.data)
```

### React: Lees Config

```typescript
import { supabase } from '@/lib/supabase'

// Get app config
const { data } = await supabase
  .from('app_configuration')
  .select('config_value')
  .eq('app_id', appId)
  .eq('config_key', 'confidence_threshold')
  .is('organization_id', null)
  .single()

const threshold = parseFloat(data.config_value)
```

### SQL: Direct Query

```sql
-- Get specific config
SELECT get_app_config('werkbon-checker', 'confidence_threshold');
-- Returns: '0.85'

-- Get with org override
SELECT get_app_config('werkbon-checker', 'confidence_threshold', 'wvc-org-uuid');
-- Returns org-specific value, or falls back to global
```

---

## 🎯 Voordelen van Supabase Config

### Editeerbaar via Admin UI
```typescript
// Admin kan settings aanpassen zonder deployment:
<ConfigEditor
  appId={appId}
  configs={appConfigs}
  onUpdate={updateConfig}
/>
```

### Per-Klant Overrides
```sql
-- Gemeente Amsterdam: strikte threshold
INSERT INTO app_configuration (app_id, organization_id, config_key, config_value)
VALUES (werkbon_checker_id, gemeente_id, 'confidence_threshold', '0.90');

-- WVC: minder strict
INSERT INTO app_configuration (app_id, organization_id, config_key, config_value)
VALUES (werkbon_checker_id, wvc_id, 'confidence_threshold', '0.80');
```

### Audit Trail
```sql
-- Wie heeft wat aangepast?
SELECT
    config_key,
    config_value,
    updated_by,
    updated_at
FROM app_configuration
WHERE app_id = werkbon_checker_id
ORDER BY updated_at DESC;
```

---

## 📚 Volgende Stappen

1. ✅ .env updated met Supabase credentials
2. ✅ Python scripts lezen credentials uit .env
3. ✅ Created `003_app_configuration.sql` schema
4. ✅ Created `config_service.py` helper with automatic type parsing
5. ✅ Created `test_config_service.py` verification script
6. ✅ Created migration guide and examples
7. ⏳ Deploy `003_app_configuration.sql` naar Supabase (SQL Editor)
8. ⏳ Test config service: `python scripts/test_config_service.py`
9. ⏳ Migrate classifier.py to use config service
10. ⏳ Migrate Streamlit pages to use config service
11. ⏳ Build React admin UI voor config management

**Status: Config Service Implementation Complete! Ready for Deployment** 🎉

**Next Action:**
1. Open Supabase SQL Editor
2. Run `sql/003_app_configuration.sql`
3. Test: `python scripts/test_config_service.py`
4. Start migrating services to use `get_app_config()`
