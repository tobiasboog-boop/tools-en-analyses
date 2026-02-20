# Setup Guide voor Collega - Contract Checker Pilot

**Doel:** Lokaal testen van werkbon classificatie en prompt engineering

---

## 🎯 Huidige Status (Pilot)

**LLM Configuratie:**
- ✅ **contract_generation** → Claude Sonnet 4 (Cloud API)
- ✅ **werkbon_classification** → Claude Sonnet 4 (Cloud API)

**Waarom Claude overal?**
- Snel starten (geen Mistral API key nodig nu)
- Bekende kwaliteit
- Later makkelijk switchen naar Mistral (76% goedkoper)

---

## 📋 Setup Stappen (30 minuten)

### 1. Clone Repository

```bash
cd c:/Projects
git clone <repo-url> contract-check
cd contract-check
git checkout feature/llm-configuration
```

### 2. Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate
.venv\Scripts\activate  # Windows
# of: source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables (BELANGRIJK!)

**Methode A: Vraag Mark om credentials (AANBEVOLEN)**

```bash
# Kopieer template
copy .env.colleague .env

# Vraag Mark om te vullen:
# - DB_PASSWORD
# - SUPABASE_ANON_KEY
# - SUPABASE_SERVICE_KEY
# - ANTHROPIC_API_KEY
```

**VEILIGE MANIEREN om credentials te delen:**
- ✅ 1Password / Bitwarden shared vault
- ✅ Encrypted file (7-Zip met wachtwoord)
- ✅ Teams privé chat met auto-delete
- ❌ NOOIT via email!
- ❌ NOOIT in Git committen!

**Methode B: Eigen API keys (als je die hebt)**

- Anthropic: https://console.anthropic.com/
- Supabase: Gebruik dezelfde als Mark (shared project)

### 4. Contracts Folder

**Pas aan in .env:**
```bash
CONTRACTS_FOLDER=C:/Users/JOUW_NAAM/OneDrive - Notifica B.V/.../Contracts
```

Of vraag Mark om lokale kopie van contracts folder.

### 5. Test Setup

```bash
# Test database connectie
python scripts/verify_app_config_simple.py

# Expected output:
# [OK] app_configuration table EXISTS
# [OK] Found 5+ configuration entries
```

### 6. Start Streamlit

```bash
streamlit run app/app.py
```

**Open:** http://localhost:8501

---

## 🧪 Testen: Werkbon Classificatie

### Stap 1: Upload Werkbon

1. Ga naar "Quick Classification" pagina
2. Upload een test werkbon
3. Klik "Classificeer"

### Stap 2: Check Logs

**In terminal waar streamlit draait:**
```
[LLM] Using provider: anthropic
[LLM] Model: claude-sonnet-4-20250514
[LLM] Tokens: 245 in, 89 out
[LLM] Cost: €0.000123
```

### Stap 3: Check Supabase

**Ga naar Supabase Table Editor:**
- Tabel: `llm_usage_logs`
- Zie nieuwe entry met:
  - `provider_code`: 'anthropic'
  - `model_code`: 'claude-sonnet-4-20250514'
  - `input_tokens`, `output_tokens`, `total_cost`

---

## ✏️ Prompt Engineering Workflow

### Huidige Prompts

**System Prompt:** [src/services/classifier.py](../src/services/classifier.py)
- Lijn 21-49: `DEFAULT_SYSTEM_PROMPT`
- Of in database: `client_config` tabel

**User Message:** [src/services/classifier.py](../src/services/classifier.py)
- Lijn 128-134: Contract + Werkbon samenstelling

### Prompts Aanpassen

**Optie 1: Code (voor snelle tests)**

```python
# src/services/classifier.py - Lijn 21
DEFAULT_SYSTEM_PROMPT = """
JE NIEUWE PROMPT HIER...

Test andere instructies:
- Meer nadruk op bepaalde aspecten
- Andere voorbeelden
- Strengere criteria
etc.
"""
```

**Restart Streamlit** → Test direct!

**Optie 2: Database (voor productie)**

```sql
-- In Supabase SQL Editor
UPDATE client_config
SET classification_instructions = 'NIEUWE INSTRUCTIES...'
WHERE client_code = 'WVC';
```

### Test Resultaten Vergelijken

**Log resultaten:**
```python
# Voor elke test:
print(f"Prompt versie: v2-stricter")
print(f"Classificatie: {result['classificatie']}")
print(f"Score: {result['mapping_score']}")
print(f"Toelichting: {result['toelichting']}")
```

**Exporteer usage logs:**
```sql
SELECT
    created_at,
    input_tokens,
    output_tokens,
    total_cost,
    -- Metadata over prompt versie (voeg toe als custom field)
FROM llm_usage_logs
WHERE created_at >= NOW() - INTERVAL '1 day'
ORDER BY created_at DESC;
```

---

## 🔄 Later: Switchen naar Mistral (76% goedkoper)

**Als je Mistral wilt testen:**

### Stap 1: API Key

```bash
# https://console.mistral.ai/
# Krijg API key

# .env
MISTRAL_API_KEY=sk-...
```

### Stap 2: Update Config (SQL)

```sql
-- In Supabase SQL Editor
UPDATE llm_configurations
SET model_id = (
    SELECT id FROM llm_models
    WHERE model_code = 'mistral-large-latest'
)
WHERE action_type = 'werkbon_classification'
  AND organization_id IS NULL;
```

### Stap 3: Test

```bash
# Restart streamlit
# Classificeer werkbon
# Check logs: "Using provider: mistral"
```

**Resultaat:**
- ✅ 76% goedkoper (€0.80/€2.40 vs €3.00/€15.00 per 1M tokens)
- ✅ Sneller (Mistral is lichter)
- ⚠️ Mogelijk andere output style (test kwaliteit!)

---

## 📊 Token Usage Monitoren

```sql
-- Daily costs per provider
SELECT
    DATE(created_at) as date,
    provider_code,
    COUNT(*) as requests,
    SUM(input_tokens) as total_input,
    SUM(output_tokens) as total_output,
    SUM(total_cost) as cost_eur
FROM llm_usage_logs
WHERE app_id = (SELECT id FROM apps WHERE code = 'werkbon-checker')
GROUP BY DATE(created_at), provider_code
ORDER BY date DESC;
```

---

## 🚨 Problemen?

### "ModuleNotFoundError: No module named 'supabase'"

```bash
pip install supabase python-dotenv
```

### "Invalid API key"

- Check `.env` file bestaat (niet `.env.colleague`!)
- Check keys zijn ingevuld (niet `VRAAG_MARK`)
- Restart terminal na .env changes

### "Contract not found"

- Check `CONTRACTS_FOLDER` path in .env
- Check folder bevat .txt bestanden
- Of: Upload contract via Streamlit UI

### Feature flag werkt niet

```bash
# .env - Check deze regel:
USE_NEW_LLM_SYSTEM=true  # ← Moet true zijn!

# Restart Streamlit na wijziging
```

---

## 📚 Documentatie

**Volledige guides:**
- [LLM_CONFIGURATION_README.md](LLM_CONFIGURATION_README.md) - Complete overview
- [PILOT_DEPLOYMENT.md](PILOT_DEPLOYMENT.md) - Deployment guide
- [configuration_management.md](configuration_management.md) - Config hierarchy

**Code:**
- [classifier.py](../src/services/classifier.py) - Werkbon classificatie
- [llm_service.py](../src/services/llm_service.py) - LLM abstraction

---

## 💬 Vragen?

Vraag Mark over:
- Credentials delen (veilig!)
- Supabase toegang
- VPS4 SSH keys (voor deployment)
- Best practices prompt engineering

---

**Veel succes met testen!** 🚀

P.S. Als je een goede prompt variant vindt, deel dan via Git commit!
