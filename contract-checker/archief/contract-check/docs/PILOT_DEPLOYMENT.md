# Pilot Deployment Guide - Pragmatische Aanpak

## 🎯 Pilot Strategie: Minimaal & Veilig

### Filosofie
- **API Keys blijven in .env** (security best practice)
- **LLM configuratie in Supabase** (flexibiliteit zonder deployment)
- **Feature flag voor rollback** (veiligheid)
- **GEEN admin UI nodig** (tijd besparen, komt later)
- **Gradual migration** (beide systemen naast elkaar)

---

## 🔐 Security: Waarom API Keys NIET in Supabase?

**NOOIT API keys in database:**
- ❌ Database dumps bevatten dan keys
- ❌ Meer mensen hebben DB toegang dan server toegang
- ❌ Database hack = alle keys weg
- ❌ Logs kunnen keys lekken
- ❌ Moeilijker te roteren

**WEL in Supabase:**
```sql
-- llm_providers table
api_key_env_var = 'ANTHROPIC_API_KEY'  -- ✅ Verwijzing naar env var naam
```

**NIET in Supabase:**
```sql
api_key = 'sk-ant-...'  -- ❌ NEVER! Echte key hoort in .env
```

---

## 📋 Deployment Stappen (30 minuten)

### Stap 1: Deploy Schema (5 min)

```sql
-- In Supabase SQL Editor:
-- Paste & run: sql/003_app_configuration.sql
```

**Verificatie:**
```bash
python scripts/test_config_service.py
```

Verwacht output:
```
[1] Individual Configs:
  confidence_threshold: 0.85 (float)
  max_batch_size: 100 (int)
  feature_quick_classification: True (bool)

[OK] Config service working correctly!
```

---

### Stap 2: Feature Flag Instellen (1 min)

**Optie A: Nieuwe systeem ENABLED (aanbevolen voor pilot)**

`.env` (al zo):
```bash
USE_NEW_LLM_SYSTEM=true  # Gebruik Supabase config (Mistral + Claude)
```

**Optie B: Nieuwe systeem DISABLED (noodremrem)**

`.env`:
```bash
USE_NEW_LLM_SYSTEM=false  # Fallback naar oude systeem (alleen Claude)
```

---

### Stap 3: Test Lokaal (10 min)

```bash
# Start Streamlit
streamlit run app/app.py
```

**Test scenario's:**

1. **Quick Classification pagina**
   - Upload 1 werkbon
   - Classificeer
   - Check console logs: `[LLM] Using provider: mistral`

2. **Contract LLM Ready Maken**
   - Upload contract
   - Genereer LLM-ready versie
   - Check console logs: `[LLM] Using provider: anthropic`

3. **Check Supabase**
   - Open Supabase Table Editor
   - Ga naar `llm_usage_logs` tabel
   - Zie nieuwe entries met:
     - `provider_code`: 'mistral' (werkbon) en 'anthropic' (contract)
     - `input_tokens`, `output_tokens`, `total_cost`

---

### Stap 4: Deploy naar VPS4 (15 min)

#### 4.1 Update .env op VPS4

```bash
ssh vps4
cd /opt/notifica/contract-checker
nano .env
```

**Voeg toe:**
```bash
# LLM Configuration System
USE_NEW_LLM_SYSTEM=true
SUPABASE_URL=https://usxstdmeljiclmcbjgvu.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc...

# LLM API Keys (already there, keep as-is)
ANTHROPIC_API_KEY=sk-ant-...
```

#### 4.2 Update Code

```bash
# Pull latest code
git fetch origin
git checkout feature/llm-configuration
git pull

# Install dependencies
source venv/bin/activate
pip install supabase python-dotenv
```

#### 4.3 Restart Service

```bash
sudo systemctl restart contract-checker-pilot
journalctl -u contract-checker-pilot -f
```

**Check logs voor:**
```
[OK] LLM service initialized
[OK] Config service initialized
```

---

## 🎛️ Wat Wordt Nu Gestuurd door Supabase?

### 1. LLM Model Selectie (llm_configurations)

**Al deployed in `002_llm_configuration_integrated.sql`:**

```sql
-- Default configs (priority 100)
werkbon-checker + werkbon_classification → Mistral Large (€0.80/€2.40)
werkbon-checker + contract_generation → Claude Sonnet 4 (€3.00/€15.00)
```

**Resultaat:**
- Werkbon classificatie gebruikt **Mistral** (76% goedkoper!)
- Contract generatie gebruikt **Claude** (kwaliteit!)

### 2. App Configuratie (app_configuration)

**Nieuw deployed in `003_app_configuration.sql`:**

```sql
confidence_threshold = 0.85
max_batch_size = 100
feature_quick_classification = true
feature_contract_generation = true
```

**Gebruik in code:**
```python
from src.services.config_service import get_app_config

# Leest automatisch uit Supabase
threshold = get_app_config('confidence_threshold', default=0.85)
```

---

## 🔍 Monitoring: Wat Te Checken

### Check 1: Token Usage Logs

```sql
-- In Supabase SQL Editor:
SELECT
    created_at,
    provider_code,
    model_code,
    input_tokens,
    output_tokens,
    total_cost
FROM llm_usage_logs
ORDER BY created_at DESC
LIMIT 20;
```

**Verwacht:**
- `provider_code = 'mistral'` voor werkbon classificaties
- `provider_code = 'anthropic'` voor contract generatie
- `total_cost` in EUR (bijv. 0.000123)

### Check 2: Cost Per Day

```sql
SELECT
    DATE(created_at) as date,
    provider_code,
    COUNT(*) as requests,
    SUM(total_cost) as daily_cost_eur
FROM llm_usage_logs
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at), provider_code
ORDER BY date DESC;
```

**Verwacht besparingen:**
- Dag met 100 werkbon classificaties:
  - OUD (alleen Claude): €0.975
  - NIEUW (Mistral): €0.236
  - **Besparing: €0.739 (76%)**

### Check 3: Feature Flag Status

```bash
# On VPS4
cat .env | grep USE_NEW_LLM_SYSTEM
```

---

## 🚨 Rollback Plan

### Scenario 1: Direct Rollback (Emergency)

**Als nieuwe systeem problemen geeft:**

```bash
# On VPS4
nano .env
# Zet: USE_NEW_LLM_SYSTEM=false

sudo systemctl restart contract-checker-pilot
```

**Resultaat:** Systeem valt terug naar oude code (direct Anthropic client)

### Scenario 2: Gradual Rollback

**Als alleen bepaalde organisaties problemen geven:**

```python
# In code (temporary patch):
if werkbon.debiteur_code == "problematic_client":
    # Use old system for this client
    self.use_new_system = False
```

---

## 📊 Success Criteria Pilot

**Week 1:**
- [ ] Alle classificaties gebruiken Mistral
- [ ] Alle contract generaties gebruiken Claude
- [ ] Token usage logs vullen zich
- [ ] Geen errors in logs
- [ ] Cost tracking werkt

**Week 2:**
- [ ] Cost besparingen zichtbaar (>70%)
- [ ] Performance gelijk of beter
- [ ] Classificatie kwaliteit gelijk of beter

**Week 3:**
- [ ] Feature flag naar permanent enabled
- [ ] Old code cleanup (remove fallback)
- [ ] Start met admin UI ontwikkeling

---

## ❓ FAQ Pilot

### Kan ik per klant een ander model kiezen?

**Ja! Maar niet via UI (pilot fase):**

```sql
-- Direct in Supabase voor premium klant (bijv. WVC)
INSERT INTO llm_configurations (
    app_id,
    organization_id,  -- UUID van WVC
    action_type,
    model_id,  -- UUID van Claude Sonnet 4
    priority
) VALUES (
    (SELECT id FROM apps WHERE code = 'werkbon-checker'),
    (SELECT id FROM organizations WHERE name = 'WVC'),
    'werkbon_classification',
    (SELECT id FROM llm_models WHERE model_code = 'claude-sonnet-4-20250514'),
    200  -- Hogere priority dan default (100)
);
```

**Resultaat:** WVC krijgt Claude voor alles (premium), rest krijgt Mistral

### Wat als Supabase down is?

**Graceful fallback:**
```python
# In config_service.py (line ~60)
try:
    value = self.client.rpc('get_app_config', ...).execute()
    return value.data
except Exception as e:
    print(f"Supabase error: {e}, using default")
    return default  # 0.85, 100, true, etc.
```

**App blijft werken met sensible defaults!**

### Hoe zie ik welk model gebruikt werd?

**In logs (journalctl):**
```
[2024-01-30 14:23:45] LLM Generate: action=werkbon_classification, model=mistral-large-latest
[2024-01-30 14:23:47] LLM Response: tokens=245/89, cost=€0.000123, latency=2340ms
```

**In Supabase:**
```sql
SELECT * FROM llm_usage_logs ORDER BY created_at DESC LIMIT 1;
```

### Kan ik terug naar alleen Claude?

**Ja, 2 opties:**

**Optie 1: Feature flag (rollback naar oude code):**
```bash
USE_NEW_LLM_SYSTEM=false
```

**Optie 2: Update Supabase config (gebruik nieuwe code, maar Claude overal):**
```sql
UPDATE llm_configurations
SET model_id = (SELECT id FROM llm_models WHERE model_code = 'claude-sonnet-4-20250514')
WHERE action_type = 'werkbon_classification';
```

---

## 🎉 Volgende Stappen na Pilot

**Als pilot succesvol:**

1. **Week 4:** Feature flag verwijderen (permanent enabled)
2. **Week 5:** Admin UI bouwen in React
3. **Week 6:** Meer LLM providers toevoegen (OpenAI, Local)
4. **Week 7:** Auto-scaling based on costs
5. **Week 8:** A/B testing verschillende modellen

---

## 📞 Support

**Bij problemen:**

1. Check logs: `journalctl -u contract-checker-pilot -f`
2. Test config: `python scripts/test_config_service.py`
3. Rollback: Set `USE_NEW_LLM_SYSTEM=false` in .env
4. Check deze documenten:
   - [LLM_CONFIGURATION_README.md](LLM_CONFIGURATION_README.md)
   - [deployment_checklist.md](deployment_checklist.md)
   - [configuration_management.md](configuration_management.md)

---

**Pragmatisch, Veilig, Geleidelijk** ✅

API keys blijven veilig in .env, configuratie flexibel in Supabase, met rollback optie!
