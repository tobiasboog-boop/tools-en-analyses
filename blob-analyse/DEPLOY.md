# BLOB Analyse - Streamlit Cloud Deployment

## Stap 1: Push naar GitHub

```bash
cd /c/projects/notifica_app
git add apps/tools-analyses/blob-analyse/
git commit -m "BLOB analyse app - gereed voor deployment"
git push origin master
```

## Stap 2: Deploy op Streamlit Cloud

1. Ga naar **https://share.streamlit.io/**
2. Log in met GitHub account (mark-notifica)
3. Klik **"New app"**
4. Configuratie:
   - **Repository**: `mark-notifica/notifica-app`
   - **Branch**: `master`
   - **Main file path**: `apps/tools-analyses/blob-analyse/app.py`
   - **App URL** (custom): `blob-analyse` of `zenith-sla-tracker`

## Stap 3: Secrets configureren

In Streamlit Cloud app settings, ga naar **"Secrets"** en voeg toe:

```toml
NOTIFICA_API_URL = "https://app.notifica.nl"
NOTIFICA_APP_KEY = "9712ce13949416f007765bf6f023c9da6e6ce1633494466d306082c288b814ff"
APP_PASSWORD = "z&fo@GeVqZ%COFBRsWmjX$sV"
```

## Stap 4: Deploy

Klik **"Deploy!"** - de app start automatisch.

## URL

Na deployment bereikbaar op:
- **https://blob-analyse.streamlit.app/** (of jouw gekozen naam)

## Wachtwoord voor eindgebruiker

- Wachtwoord: `z&fo@GeVqZ%COFBRsWmjX$sV`
- Kan later aangepast worden in Secrets

## Requirements

De app gebruikt:
- Notifica Data API (SDK via `apps/_sdk/`)
- Python packages uit `requirements.txt`
- Secrets uit Streamlit Cloud (NIET .env in productie)

## Updates deployen

Bij wijzigingen:

```bash
git add apps/tools-analyses/blob-analyse/
git commit -m "Update BLOB analyse"
git push
```

Streamlit Cloud detecteert wijzigingen en redeploy automatisch.
