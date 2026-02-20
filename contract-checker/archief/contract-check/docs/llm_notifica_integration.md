## LLM Configuration - Notifica App Integration

## Overzicht

Het LLM configuratie systeem is volledig geïntegreerd met de Notifica App infrastructuur. Dit document beschrijft hoe alles samenwerkt.

---

## Database Integratie

### Bestaande Notifica Tabellen (gebruikt door LLM systeem)

```
apps
├── id (uuid)
├── code (varchar)          → 'werkbon-checker', 'voorraad-dashboard'
├── name (varchar)          → 'Werkbon Contract Checker'
└── ...

organizations
├── id (uuid)
├── name (varchar)          → 'WVC Groep', 'Gemeente Amsterdam'
├── organization_type       → 'customer', 'internal'
└── ...

user_profiles
├── id (uuid)
├── full_name
├── organization_id         → FK naar organizations
└── ...

app_permissions
├── app_id                  → FK naar apps
├── organization_id         → FK naar organizations
├── permission_level        → 'user', 'admin', 'readonly'
└── ...
```

### Nieuwe LLM Tabellen

```
llm_providers
├── code                    → 'anthropic', 'mistral', 'openai', 'local'
├── name                    → 'Anthropic (Claude)', 'Mistral AI'
└── ...

llm_models
├── provider_id             → FK naar llm_providers
├── model_code              → 'claude-sonnet-4-20250514'
├── cost_per_input_token    → 3.00 (per 1M tokens)
└── ...

llm_configurations
├── app_id                  → FK naar apps (welke app)
├── organization_id         → FK naar organizations (welke klant, NULL = alle)
├── action_type             → 'contract_generation', 'werkbon_classification'
├── model_id                → FK naar llm_models (welk model)
└── ...

llm_usage_logs
├── app_id                  → FK naar apps
├── organization_id         → FK naar organizations
├── user_id                 → FK naar user_profiles
├── provider_code           → Denormalized 'anthropic'
├── model_code              → Denormalized 'claude-sonnet-4-20250514'
├── input_tokens, output_tokens, total_cost
└── ...
```

---

## Hoe Het Werkt

### 1. Configuration Lookup (Python Backend)

```python
# Contract Checker app wil classificeren
app_code = 'werkbon-checker'
organization_id = 'uuid-of-wvc'
action_type = 'werkbon_classification'

# Query:
SELECT
    c.*,
    m.model_code,
    p.code as provider_code,
    m.cost_per_input_token,
    m.cost_per_output_token
FROM llm_configurations c
JOIN llm_models m ON c.model_id = m.id
JOIN llm_providers p ON m.provider_id = p.id
JOIN apps a ON c.app_id = a.id
WHERE a.code = 'werkbon-checker'
  AND c.action_type = 'werkbon_classification'
  AND (c.organization_id = 'uuid-of-wvc' OR c.organization_id IS NULL)
  AND c.is_active = true
ORDER BY
    c.organization_id NULLS LAST,  -- Client-specific first
    c.priority DESC
LIMIT 1;

# Result:
# - WVC specifiek: Claude Sonnet 4
# - Of default: Mistral Large
```

### 2. Usage Logging

```python
# Na LLM call
INSERT INTO llm_usage_logs (
    app_id,                     -- From apps.id where code = 'werkbon-checker'
    organization_id,            -- WVC's uuid
    user_id,                    -- Current user's uuid
    action_type,                -- 'werkbon_classification'
    provider_code,              -- 'mistral'
    model_code,                 -- 'mistral-large-latest'
    input_tokens,               -- 2500
    output_tokens,              -- 150
    input_cost,                 -- 0.002 EUR
    output_cost,                -- 0.00036 EUR
    latency_ms,                 -- 1250
    success,                    -- true
    entity_type,                -- 'werkbon'
    entity_id                   -- '12345'
) VALUES (...);
```

### 3. Multi-Tenant Cost Tracking

```sql
-- Kosten per klant per maand
SELECT
    o.name as klant,
    a.name as app,
    DATE_TRUNC('month', l.created_at) as maand,
    COUNT(*) as aanvragen,
    SUM(l.total_tokens) as tokens,
    SUM(l.total_cost) as kosten
FROM llm_usage_logs l
JOIN organizations o ON l.organization_id = o.id
JOIN apps a ON l.app_id = a.id
WHERE l.created_at >= '2025-01-01'
GROUP BY o.name, a.name, DATE_TRUNC('month', l.created_at)
ORDER BY kosten DESC;
```

---

## Configuratie Voorbeelden

### Default: Alle Klanten

```sql
-- Mistral voor bulk werkbon classificatie
INSERT INTO llm_configurations (
    app_id,              -- (SELECT id FROM apps WHERE code = 'werkbon-checker')
    organization_id,     -- NULL = voor alle klanten
    action_type,         -- 'werkbon_classification'
    model_id,            -- (SELECT id FROM llm_models WHERE model_code = 'mistral-large-latest')
    max_tokens,          -- 1024
    temperature,         -- 0.0
    priority             -- 100
) VALUES (...);
```

### Override: Premium Klant (WVC)

```sql
-- Claude voor WVC (premium)
INSERT INTO llm_configurations (
    app_id,              -- (SELECT id FROM apps WHERE code = 'werkbon-checker')
    organization_id,     -- (SELECT id FROM organizations WHERE name = 'WVC Groep')
    action_type,         -- 'werkbon_classification'
    model_id,            -- (SELECT id FROM llm_models WHERE model_code = 'claude-sonnet-4-20250514')
    max_tokens,          -- 1024
    temperature,         -- 0.0
    priority             -- 200 (hoger dan default!)
) VALUES (...);
```

### Resultaat

- **Gemeente Amsterdam** → Gebruikt **Mistral** (default)
- **WVC Groep** → Gebruikt **Claude** (premium override)
- **Kosten:** WVC betaalt meer, maar krijgt hogere kwaliteit

---

## React Frontend Integration

### 1. Configuratie UI (Admin Panel)

```typescript
// pages/admin/LLMConfiguration.tsx
import { supabase } from '@/lib/supabase'

// Haal apps op
const { data: apps } = await supabase
  .from('apps')
  .select('*')
  .eq('is_active', true)

// Haal organizations op
const { data: orgs } = await supabase
  .from('organizations')
  .select('*')
  .eq('is_active', true)

// Haal beschikbare modellen op
const { data: models } = await supabase
  .from('llm_models')
  .select(`
    *,
    llm_providers (
      code,
      name
    )
  `)
  .eq('is_active', true)

// Maak nieuwe configuratie
const { data } = await supabase
  .from('llm_configurations')
  .insert({
    app_id: selectedApp.id,
    organization_id: selectedOrg?.id || null,
    action_type: 'werkbon_classification',
    model_id: selectedModel.id,
    max_tokens: 1024,
    temperature: 0.0,
    priority: 100
  })
```

### 2. Usage Dashboard

```typescript
// pages/admin/LLMUsage.tsx
import { supabase } from '@/lib/supabase'

// Gebruik de view voor easy access
const { data: usage } = await supabase
  .from('llm_cost_per_organization')
  .select('*')
  .gte('month', '2025-01-01')
  .order('total_cost', { ascending: false })

// Of direct query
const { data: recentCalls } = await supabase
  .from('llm_recent_usage')
  .select('*')
  .limit(50)
```

### 3. User-Facing Stats

```typescript
// Voor end-users: hun eigen org usage
const { data } = await supabase
  .from('llm_usage_logs')
  .select('*')
  .eq('organization_id', currentUser.organization_id)
  .gte('created_at', startDate)
  .lte('created_at', endDate)

// RLS zorgt ervoor dat users alleen eigen org zien
```

---

## Python Backend Update

### Oude Code (application_id string)

```python
# Oude manier
llm_service = LLMService(application_id="contract-checker")
```

### Nieuwe Code (app_id uuid)

```python
# config_service.py update
class LLMConfigService:
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        app_code: str = "werkbon-checker"  # App code instead of ID
    ):
        self.app_code = app_code
        # Haal app_id op bij init
        result = self.client.table("apps").select("id").eq("code", app_code).single().execute()
        self.app_id = result.data["id"]

    def get_provider(self, action_type, organization_id=None):
        # Query met app_id
        query = (
            self.client
            .table("llm_configurations")
            .select("""
                *,
                llm_models (
                    model_code,
                    llm_providers (
                        code,
                        default_api_endpoint
                    )
                ),
                cost_per_input_token,
                cost_per_output_token
            """)
            .eq("app_id", self.app_id)
            .eq("action_type", action_type)
            .eq("is_active", True)
        )

        # Client-specific of default
        if organization_id:
            result = query.eq("organization_id", organization_id).limit(1).execute()
            if result.data:
                return result.data[0]

        # Fallback to default (organization_id = NULL)
        result = query.is_("organization_id", "null").limit(1).execute()
        return result.data[0] if result.data else None
```

---

## Deployment Checklist

### 1. Supabase Setup

```bash
# SSH naar VPS4 of run lokaal
psql -h usxstdmeljiclmcbjgvu.supabase.co -U postgres -d postgres

# Of via Supabase SQL Editor:
# 1. Run: sql/001_extend_schema.sql (als nog niet gedaan)
# 2. Run: sql/002_llm_configuration_integrated.sql
```

### 2. Environment Variables

```bash
# Contract Checker .env
SUPABASE_URL=https://usxstdmeljiclmcbjgvu.supabase.co
SUPABASE_KEY=<anon-key>

# LLM Provider Keys
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
```

### 3. Python Code Update

```bash
cd /opt/notifica/contract-checker

# Update code to use new schema
git pull

# Install dependencies (if updated)
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart contract-checker-pilot
```

### 4. React App Update

```bash
cd /opt/notifica/app

# Pull latest code
git pull

# Build
npm run build

# Nginx restart
sudo systemctl reload nginx
```

---

## Migratie Strategie

### Fase 1: Database Setup (Nu)
1. ✅ Run `001_extend_schema.sql` (apps, organizations, etc.)
2. ✅ Run `002_llm_configuration_integrated.sql` (LLM tables)
3. ✅ Verify seed data (providers, models, default configs)

### Fase 2: Python Backend (Week 1)
1. Update `llm_config_service.py` to use `app_code`/`app_id`
2. Update `llm_usage_logger.py` to log `app_id` and `organization_id`
3. Test with Contract Checker
4. Deploy to VPS4

### Fase 3: React Frontend (Week 2-3)
1. Build admin UI voor LLM configuration
2. Build usage dashboard
3. Integreer met bestaande Notifica app
4. User-facing usage stats

### Fase 4: Andere Apps (Week 4+)
1. Voorraad Dashboard LLM integratie
2. Andere toekomstige apps
3. Shared usage analytics

---

## Voordelen van Deze Architectuur

### ✅ Multi-Tenant Ready
- Elke klant kan eigen LLM configuratie krijgen
- Kosten worden per klant getrackt
- RLS policies beschermen data

### ✅ Multi-App Support
- Meerdere apps delen dezelfde LLM infrastructuur
- Centrale cost tracking
- Unified admin interface

### ✅ Flexible Configuration
- Per app, per klant, per actie type
- Priority-based fallback
- Easy to add nieuwe providers/models

### ✅ Cost Optimization
- Cheap models voor bulk work (Mistral)
- Premium models voor premium clients (Claude)
- Future: Local models voor zero cost

### ✅ Audit Trail
- Elke LLM call wordt gelogd
- User tracking
- Performance metrics
- Error monitoring

---

## Voorbeeld: Complete Flow

### 1. User (Jan bij WVC) opent Contract Checker

```typescript
// React: Check permissions
const { data: permission } = await supabase
  .from('app_permissions')
  .select('*')
  .eq('app_id', contractCheckerApp.id)
  .eq('organization_id', currentUser.organization_id)
  .single()

// Jan heeft toegang!
```

### 2. Jan uploadt werkbon

```python
# Python Backend: Classificeer werkbon
llm_service = LLMService(app_code="werkbon-checker")

response = llm_service.generate(
    system_prompt="...",
    user_message="...",
    action_type="werkbon_classification",
    organization_id=jan.organization_id,  # WVC uuid
    user_id=jan.id
)

# Lookup: WVC heeft Claude override (premium)
# Result: Claude Sonnet 4 wordt gebruikt
# Cost: €0.008 (hoger, maar betere kwaliteit)
# Log entry gemaakt met alle details
```

### 3. Admin bekijkt kosten

```typescript
// React Admin Dashboard
const { data } = await supabase
  .from('llm_cost_per_organization')
  .select('*')
  .eq('organization_id', wvcOrg.id)
  .gte('month', '2025-01-01')

// Shows:
// - WVC: €145 (Claude usage)
// - Gemeente: €23 (Mistral usage)
```

---

## Support

Vragen of problemen? Check:
- Database: Supabase dashboard @ https://supabase.com/dashboard
- Logs: VPS4 `/var/log/nginx/` en `journalctl`
- Schema: `sql/002_llm_configuration_integrated.sql`
