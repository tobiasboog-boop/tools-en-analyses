# Deployment Guide - Maandrapportage Zenith Security

## 🎯 Overzicht

Deze guide helpt bij het veilig deployen van de maandrapportage tool naar Streamlit Cloud.

**Belangrijkste kenmerken:**
- ✅ **Geen hardcoded credentials** - alles via secrets
- ✅ **Fallback naar JSON** - werkt ook zonder database
- ✅ **Production-ready** - veilig te publiceren

---

## 📋 Pre-deployment Checklist

### 1. Security Check
- [ ] Geen credentials in code (check `app.py`)
- [ ] `.streamlit/secrets.toml` staat in `.gitignore`
- [ ] Database user is **read-only**
- [ ] IP whitelisting actief op database

### 2. Code Ready
- [ ] Alle changes gecommit
- [ ] Requirements.txt up-to-date
- [ ] App werkt lokaal met JSON fallback

### 3. Techniek Afstemming
- [ ] Database credentials ontvangen
- [ ] Bevestiging dat Streamlit Cloud IP's whitelisted zijn
- [ ] Read-only user rechten gecontroleerd

---

## 🚀 Deployment Stappen

### Stap 1: Lokaal Testen (zonder database)

```bash
cd C:\projects\blob-analyse

# Installeer dependencies
pip install -r requirements.txt

# Run app (gebruikt JSON fallback)
streamlit run app.py
```

**Verwacht resultaat:**
- Sidebar toont: "🟡 JSON Files (sample)"
- App werkt met data uit `data/sample_data.json`

---

### Stap 2: Lokaal Testen (met database)

**Alleen als je toegang hebt tot de database vanuit je netwerk!**

1. **Maak secrets file:**
   ```bash
   cd .streamlit
   cp secrets.toml.example secrets.toml
   ```

2. **Vul credentials in:** (krijg je van Techniek)
   ```toml
   [database]
   host = "217.160.16.105"
   port = 5432
   database = "1229"
   user = "steamlit_1229"
   password = "ECHTE_PASSWORD_HIER"
   ```

3. **Test connectie:**
   ```bash
   streamlit run app.py
   ```

**Verwacht resultaat:**
- Sidebar toont: "🟢 Database (live)"
- Data komt uit database (als bereikbaar)

---

### Stap 3: Push naar GitHub

```bash
git add .
git commit -m "Maandrapportage tool - production ready"
git push origin main
```

**✅ Safety check:**
- `.streamlit/secrets.toml` wordt **NIET** gepusht (staat in `.gitignore`)
- Alleen `.streamlit/secrets.toml.example` (zonder echte credentials) wordt gepusht

---

### Stap 4: Deploy naar Streamlit Cloud

1. **Ga naar:** https://share.streamlit.io/

2. **New app aanmaken:**
   - Repository: `tobiasboog-boop/blob-analyse`
   - Branch: `main`
   - Main file: `app.py`

3. **Advanced settings:**
   - Python version: `3.10` of hoger

---

### Stap 5: Configureer Secrets op Streamlit Cloud

Dit is de **belangrijkste stap** voor database toegang!

1. **In Streamlit Cloud:** Ga naar je app
2. **Klik op:** ⚙️ Settings
3. **Navigeer naar:** Secrets
4. **Plak de volgende inhoud:**

```toml
[database]
host = "217.160.16.105"
port = 5432
database = "1229"
user = "steamlit_1229"
password = "ECHTE_PASSWORD_HIER"
```

5. **Save** en **Reboot app**

---

### Stap 6: Test de Live App

1. **Open de app URL** (bijv. `https://blob-analyse-zenith.streamlit.app`)

2. **Check de sidebar:**
   - Als "🟢 Database (live)" → Connectie werkt!
   - Als "🟡 JSON Files (sample)" → Database niet bereikbaar

3. **Test filters:**
   - Selecteer een maand
   - Selecteer een klant
   - Download CSV

4. **Test met Zenith:**
   - Laat klant inloggen
   - Test of ze hun data zien
   - Test CSV export

---

## 🔒 Security Best Practices

### ✅ Wat is VEILIG

1. **Secrets via Streamlit Cloud dashboard**
   - Credentials nooit in code
   - Encrypted opslag
   - Alleen toegankelijk voor app

2. **Read-only database user**
   - Kan alleen SELECT queries doen
   - Geen INSERT/UPDATE/DELETE
   - Beperkt tot schema `werkbonnen` en `maatwerk`

3. **IP Whitelisting**
   - Alleen Streamlit Cloud IP ranges
   - Niet publiek toegankelijk
   - Extra firewall laag

4. **HTTPS connectie**
   - Alle data encrypted in transit
   - Automatisch door Streamlit Cloud

### ❌ Wat is NIET VEILIG

1. **Credentials in code** (✅ opgelost in deze versie)
2. **Credentials in Git repository** (✅ .gitignore beschermt dit)
3. **Database zonder IP whitelist**
4. **Database user met write rechten**

---

## 🔧 Troubleshooting

### Probleem: "Database niet bereikbaar"

**Mogelijke oorzaken:**
1. Streamlit Cloud IP's niet whitelisted op database
2. Database firewall blokkeert externe toegang
3. Verkeerde credentials in secrets

**Oplossing:**
1. Check Streamlit Cloud IP ranges: [Documentatie](https://docs.streamlit.io/streamlit-community-cloud/get-started/trust-and-security)
2. Vraag Techniek om deze IP's toe te voegen
3. Test secrets syntax (TOML format)

---

### Probleem: "App toont geen data"

**Check:**
1. Is JSON fallback actief? (zie sidebar)
2. Zijn de JSON files aanwezig in `data/` folder?
3. Check app logs in Streamlit Cloud

**Oplossing:**
- Als JSON mode: Normaal, data is beschikbaar
- Als database mode maar geen data: Check database queries

---

### Probleem: "Secrets niet gevonden"

**Check:**
1. Zijn secrets correct geconfigureerd in Streamlit Cloud?
2. Is de TOML syntax correct? (geen spaties voor keys)
3. Is de app gereboot na secrets toevoegen?

**Oplossing:**
1. Ga naar Settings > Secrets
2. Check format:
   ```toml
   [database]
   host = "..."  # Met quotes!
   port = 5432   # Zonder quotes (nummer)
   ```
3. Save en Reboot

---

## 📞 Support Contacten

### Techniek (Database toegang)
- Voor: IP whitelisting, database credentials, user rechten
- Contact: Team Techniek

### Streamlit Cloud (Platform)
- Voor: Deployment issues, secrets management
- Docs: https://docs.streamlit.io/

### Notifica (Algemeen)
- Voor: Feature requests, bug reports
- Contact: Interne tickets

---

## 🎉 Succesvol Deployed?

Als alles werkt zie je:
- ✅ Sidebar: "🟢 Database (live)"
- ✅ Data laden indicator werkt
- ✅ Filters werken
- ✅ CSV download werkt
- ✅ Zenith kan inloggen en hun data zien

**Gefeliciteerd!** De maandrapportage tool is live! 🚀

---

## 📝 Changelog & Maintenance

### Versie 1.0 (2026-02-10)
- Initial release
- Streamlit secrets integratie
- JSON fallback mode
- Security hardening
- Deployment guide

### Toekomstige Updates
- Database join logica implementeren (CLOB data)
- Meer filter opties
- Excel export (ipv CSV)
- Email rapportage
- Multi-klant support (switch tussen DWH schemas)

---

**Document Versie:** 1.0
**Laatst bijgewerkt:** 2026-02-10
**Auteur:** Claude Code + Tobias
