# Deployment Bestanden voor Contract Checker Pilot

Deze folder bevat alle bestanden en documentatie voor het deployen en beheren van de Contract Checker pilot op VPS4.

## Bestanden Overzicht

### Configuratie Bestanden
- **`wvc-pilot.nginx.conf`** - Nginx reverse proxy configuratie voor HTTPS en basic auth
- **`contract-checker-pilot.service`** - Systemd service definitie voor automatisch starten
- **`deploy-pilot.sh`** - Initiële deployment script (eenmalig gebruikt bij setup)

### Deployment Scripts
- **`deploy-update.ps1`** - PowerShell script voor deployen van updates (Windows)
- **`deploy-update.sh`** - Bash script voor deployen van updates (Git Bash/WSL)

### Documentatie
- **`HANDLEIDING_PILOT_DEPLOYMENT.md`** - Complete handleiding voor initiële setup
- **`BEHEER_PILOT.md`** - Dagelijks beheer en troubleshooting
- **`QUICK_REFERENCE.md`** - Snelle referentie voor veelgebruikte commando's
- **`README.md`** - Dit bestand

---

## Quick Start: Updates Deployen

### Vanaf Windows (PowerShell):
```powershell
.\deployment\deploy-update.ps1
```

### Vanaf Git Bash / WSL:
```bash
./deployment/deploy-update.sh
```

Het script doet automatisch:
1. ✅ Backup maken van huidige versie
2. ✅ Code kopiëren naar VPS4
3. ✅ Dependencies updaten
4. ✅ Service herstarten
5. ✅ Status controleren

---

## Workflow: Ontwikkelen → Deployen

```
1. Lokaal ontwikkelen en testen
   └─> streamlit run Home.py

2. Code committen (optioneel)
   └─> git add . && git commit -m "Feature: ..."

3. Deploy naar pilot
   └─> ./deployment/deploy-update.sh

4. Testen op pilot
   └─> https://wvc-pilot.notifica.nl
```

---

## Release Management

### Semantic Versioning

Gebruik Git tags voor versie tracking:

```bash
# Bug fix (v1.0.0 → v1.0.1)
git tag -a v1.0.1 -m "Fix: Database connection timeout"

# Nieuwe feature (v1.0.1 → v1.1.0)
git tag -a v1.1.0 -m "Feature: Export naar Excel"

# Breaking change (v1.1.0 → v2.0.0)
git tag -a v2.0.0 -m "Major: Complete UI redesign"

# Push tags
git push --tags
```

### Release Checklist

Voordat je een release deployed:

- [ ] Lokaal getest met `streamlit run Home.py`
- [ ] Git commit gemaakt met duidelijke message
- [ ] Release tag aangemaakt (voor grote updates)
- [ ] Deploy script uitgevoerd
- [ ] Getest op https://wvc-pilot.notifica.nl
- [ ] Logs gecontroleerd voor errors

---

## Belangrijke Locaties

### Op VPS4
- Applicatie: `/opt/notifica/contract-checker/`
- Service: `/etc/systemd/system/contract-checker-pilot.service`
- Nginx config: `/etc/nginx/sites-available/wvc-pilot.conf`
- SSL cert: `/etc/nginx/ssl/wvc-pilot.notifica.nl.*`
- Backups: `/opt/notifica/contract-checker-backup-*.tar.gz`

### Lokaal (Windows)
- Project: `C:\Projects\contract-check\`
- Deployment scripts: `C:\Projects\contract-check\deployment\`
- SSH key: `C:\Users\markh\OneDrive - Notifica B.V\Persoonlijk\putty\id_rsa_vps4`

---

## Service Management

### Veelgebruikte Commando's

```bash
# SSH naar VPS4
ssh root@212.132.90.158

# Service herstarten
systemctl restart contract-checker-pilot

# Live logs bekijken
journalctl -u contract-checker-pilot -f

# Status checken
systemctl status contract-checker-pilot
```

---

## Troubleshooting

Voor gedetailleerde troubleshooting, zie:
- [BEHEER_PILOT.md](./BEHEER_PILOT.md#troubleshooting) - Complete troubleshooting guide
- [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#troubleshooting-cheat-sheet) - Quick fixes

**Meest voorkomende problemen:**

1. **App laadt niet** → `systemctl restart contract-checker-pilot`
2. **502 Bad Gateway** → Streamlit is down, herstart service
3. **Database error** → Check DATABASE_URL in service file
4. **SSL error** → Certificaat verlopen, run acme.sh renewal

---

## Contact & Support

**Pilot URL:** https://wvc-pilot.notifica.nl

**WVC Credentials:**
- Username: `wvc_user`
- Password: `1r2UcLtiPNmOhS1`

**Server Details:**
- Host: VPS4 (212.132.90.158)
- User: root
- Service: contract-checker-pilot.service
- Port: 8501 (internal), 443 (external)

---

## Volgende Stappen

1. **Na pilot fase:** Update naar main React app op app.notifica.nl
2. **Monitoring:** Overweeg uptime monitoring (bijv. UptimeRobot)
3. **Backups:** Automatische backup cron job overwegen
4. **Logging:** Centralized logging (bijv. naar S3 of logging service)

Voor uitfaseren instructies, zie [BEHEER_PILOT.md](./BEHEER_PILOT.md#uitfaseren-pilot)
