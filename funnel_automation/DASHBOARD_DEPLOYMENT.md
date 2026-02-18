# Dashboard Deployment & API Calls Uitleg

## Automatische API Calls

### Hoe het werkt:

**Action Dashboard (`action_dashboard.py`):**
```python
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_mailerlite_data():
    subscribers = ml.get_all_subscribers(limit=2000)
    # ... processing
    return subscribers
```

**JA, het dashboard doet automatische API calls:**
- ✅ Bij eerste load: Haalt alle MailerLite data op (1,793 subscribers)
- ✅ Daarna: Gebruikt cache voor 1 uur
- ✅ Na 1 uur: Automatisch nieuwe data ophalen bij refresh

### Rate Limiting - Bescherming

**MailerLite API:**
- ✅ Limiet: 120 requests/min
- ✅ Dashboard gebruikt: ~18 requests (1x per uur)
- ✅ **Geen probleem** - ver onder limiet

**Pipedrive API:**
- ❌ Momenteel NIET gebruikt in Action Dashboard
- ⏳ Wordt morgen toegevoegd (na quota reset 01:00)
- ⏳ Met rate limiting: max 100 requests/min

### Toekomstige bescherming (morgen):

```python
# Rate limiting voor Pipedrive (in score_leads_api.py)
import time

for person in persons:
    person['deals'] = api.get_person_deals(person_id)
    person['activities'] = api.get_person_activities(person_id)

    # Elke 50 requests: pauze van 5 seconden
    if (i+1) % 50 == 0:
        time.sleep(5)  # Voorkom rate limit
```

---

## Streamlit Cloud Deployment

### Stap 1: Voorbereiding

**1. Requirements.txt aanmaken:**
```
streamlit==1.52.2
pandas==2.2.0
requests==2.32.0
python-dotenv==1.0.0
```

**2. Secrets configureren** (voor API tokens):
```toml
# .streamlit/secrets.toml (lokaal, niet committen!)
MAILERLITE_API_TOKEN = "eyJ0eXAi..."
PIPEDRIVE_API_TOKEN = "55e6c216..."
```

**3. Git repository**:
```bash
cd c:/projects/tools_en_analyses/funnel_automation
git init
git add action_dashboard.py mailerlite_api_v2.py requirements.txt
git commit -m "Add action dashboard"
git remote add origin https://github.com/YOUR_USERNAME/funnel-automation
git push -u origin main
```

### Stap 2: Streamlit Cloud Setup

**URL:** https://share.streamlit.io/

1. **Sign in** met GitHub account
2. **New app**
3. **Repository:** `funnel-automation`
4. **Branch:** `main`
5. **Main file:** `action_dashboard.py`

### Stap 3: Secrets toevoegen in Cloud

In Streamlit Cloud dashboard:
```
Settings → Secrets → Add

[secrets]
MAILERLITE_API_TOKEN = "eyJ0eXAi..."
PIPEDRIVE_API_TOKEN = "55e6c216..."
```

### Stap 4: Code aanpassen voor Cloud

```python
# Aanpassing in action_dashboard.py voor Cloud secrets:

import streamlit as st
import os

# Lokaal: gebruik .env
# Cloud: gebruik Streamlit secrets
try:
    MAILERLITE_API_TOKEN = st.secrets["MAILERLITE_API_TOKEN"]
except:
    from dotenv import load_dotenv
    load_dotenv()
    MAILERLITE_API_TOKEN = os.getenv('MAILERLITE_API_TOKEN')
```

---

## Deployment Checklist

- [ ] Requirements.txt aanmaken
- [ ] GitHub repository aanmaken
- [ ] Code committen
- [ ] Streamlit Cloud account aanmaken
- [ ] App deployen
- [ ] Secrets configureren
- [ ] Testen in Cloud

---

## Kosten

**Streamlit Cloud:**
- ✅ **Gratis tier**: 1 private app
- ✅ Voldoende voor dit dashboard
- ✅ Auto-updates bij git push

**API Kosten:**
- ✅ MailerLite: Gratis (120 req/min)
- ✅ Pipedrive: Bestaand abonnement
- ✅ **Totaal extra: €0/maand**

---

## Monitoring

**Check dashboard health:**
```python
# Laatste API call timestamp
st.caption(f"Laatste data refresh: {datetime.now()}")

# Aantal API calls vandaag
# (TODO: implementeer API call counter)
```

**Pipedrive quota tracking:**
- Limiet: 90,000 tokens/dag
- Reset: 01:00 CET
- Monitor via: Pipedrive → Settings → API

---

## Volgende Stappen

1. ✅ **Nu**: Action Dashboard lokaal werkend
2. ⏳ **Vandaag**: Compactere presentatie hot leads
3. ⏳ **Morgen 01:00**: Pipedrive integratie toevoegen
4. ⏳ **Deze week**: Deployen naar Streamlit Cloud
5. ⏳ **Over 2-3 weken**: GA4 website tracking toevoegen

---

## Support

**Dashboard niet werkend?**
1. Check API tokens in .env
2. Check rate limits (Pipedrive vooral)
3. Check Streamlit logs: Terminal output
4. Refresh browser (Ctrl+F5)

**Deployment issues?**
1. Check GitHub repository
2. Check Streamlit Cloud logs
3. Check secrets configuratie
4. Verify requirements.txt
