# Funnel Automation - Lead Scoring Dashboard

Geautomatiseerd lead scoring systeem dat Pipedrive (CRM), MailerLite (email engagement) en GA4 (website gedrag) integreert.

## 🎯 Action Dashboard

Actiegericht dashboard dat direct laat zien wie je moet emailen of bellen.

**Live demo:** Lokaal via `streamlit run action_dashboard.py`

### Features:
- 🔥 Hot Leads (score ≥20): Direct contact
- 🟡 Warm Leads (score 10-19): Email follow-up
- 🧊 Cold Leads (score <10): Nurture campagne
- 📊 Campaign performance overzicht
- 📥 CSV export voor alle segmenten

## 🚀 Streamlit Cloud Deployment

### Stap 1: Secrets configureren

In Streamlit Cloud dashboard → Settings → Secrets, voeg toe:

```toml
MAILERLITE_API_TOKEN = "eyJ0eXAi..."
PIPEDRIVE_API_TOKEN = "55e6c216..."
GA4_PROPERTY_ID = "123456789"
```

### Stap 2: Deploy

1. Ga naar https://share.streamlit.io/
2. Sign in met GitHub
3. Klik "New app"
4. Repository: `tobiasboog-boop/tools-en-analyses`
5. Branch: `master`
6. Main file: `funnel_automation/action_dashboard.py`
7. Deploy!

## 📊 Data Bronnen

| Bron | Data | Status |
|------|------|--------|
| MailerLite API | Email engagement (1,793 subscribers) | ✅ Live |
| Pipedrive API | CRM activiteit + telefoonnummers | ⏳ Morgen (na quota reset 01:00) |
| GA4 Data API | Website gedrag | ⏳ Over 2-3 weken (data verzamelen) |

## 🔧 Lokaal draaien

```bash
cd c:/projects/tools_en_analyses/funnel_automation
pip install -r requirements.txt
streamlit run action_dashboard.py
```

**Vereist:** `.env` bestand met API tokens (zie `.streamlit/secrets.toml.example`)

## 📁 Bestanden

| Bestand | Functie |
|---------|---------|
| `action_dashboard.py` | Actiegericht Streamlit dashboard |
| `mailerlite_api_v2.py` | MailerLite API wrapper |
| `pipedrive_api.py` | Pipedrive API client |
| `ga4_data_api.py` | GA4 Data API wrapper |
| `lead_scoring.py` | Lead scoring algoritme |

## 🔒 Rate Limits

| API | Limiet | Bescherming |
|-----|--------|-------------|
| MailerLite | 120 req/min | ✅ Caching (1 uur) |
| Pipedrive | 90,000 tokens/dag | ✅ Manual reset 01:00 CET |
| GA4 | 10,000 req/dag | ✅ Caching + batch queries |

## 📞 Support

**Dashboard issues?**
1. Check API tokens in Streamlit secrets
2. Check browser console voor errors
3. Refresh (Ctrl+F5)

**Deployment issues?**
1. Verify requirements.txt
2. Check Streamlit Cloud logs
3. Validate secrets configuratie
