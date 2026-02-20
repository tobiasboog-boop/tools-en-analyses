# Quick Reference: Contract Checker Pilot

## Deployment Workflow

### 1. Lokaal Ontwikkelen & Testen

```bash
# Start lokaal om te testen
streamlit run Home.py

# Test je wijzigingen
# ...
```

### 2. Code Committen (Optioneel maar Aanbevolen)

```bash
# Stage wijzigingen
git add .

# Commit met duidelijke message
git commit -m "Feature: Nieuwe validatie regel toegevoegd"

# Push naar repo
git push

# Optioneel: Maak release tag voor belangrijke updates
git tag -a v1.1.0 -m "Release v1.1.0: Validatie verbeteringen"
git push origin v1.1.0
```

### 3. Deploy naar Pilot

**PowerShell (Windows):**
```powershell
.\deployment\deploy-update.ps1
```

**Git Bash / WSL:**
```bash
./deployment/deploy-update.sh
```

### 4. Verifiëren

1. Open browser: https://wvc-pilot.notifica.nl
2. Login met WVC credentials
3. Test de nieuwe functionaliteit

---

## Meest Gebruikte Commando's

### Deploy Update
```bash
# Snelste manier om update uit te rollen
./deployment/deploy-update.sh
```

### Service Beheer (op VPS4)
```bash
# SSH naar VPS4
ssh root@212.132.90.158

# Service herstarten
systemctl restart contract-checker-pilot

# Logs bekijken
journalctl -u contract-checker-pilot -f

# Status checken
systemctl status contract-checker-pilot
```

### Quick Fix Deploy (alleen 1 bestand)
```bash
# Alleen Home.py updaten
scp -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" Home.py root@212.132.90.158:/opt/notifica/contract-checker/

# Service herstarten
ssh -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" root@212.132.90.158 "systemctl restart contract-checker-pilot"
```

---

## Release Nummering (Semantic Versioning)

Gebruik deze conventie voor versie tags:

**v1.0.0** = Major.Minor.Patch

- **Major (1.x.x)** - Grote wijzigingen, breaking changes
  - Voorbeeld: `v2.0.0` - Complete UI redesign

- **Minor (x.1.x)** - Nieuwe features, backwards compatible
  - Voorbeeld: `v1.1.0` - Nieuwe validatie regel toegevoegd

- **Patch (x.x.1)** - Bug fixes, kleine verbeteringen
  - Voorbeeld: `v1.0.1` - Fix typo in error message

### Release Workflow

```bash
# 1. Maak wijzigingen en test lokaal
# ...

# 2. Commit changes
git add .
git commit -m "Feature: Beschrijving van wijziging"

# 3. Maak release tag
git tag -a v1.1.0 -m "Release v1.1.0: Beschrijving"

# 4. Push alles
git push && git push --tags

# 5. Deploy naar pilot
./deployment/deploy-update.sh
```

### Bekijk Releases

```bash
# Alle releases tonen
git tag

# Specifieke release info
git show v1.1.0

# Deploy specifieke release
git checkout v1.1.0
./deployment/deploy-update.sh
git checkout main
```

---

## Troubleshooting Cheat Sheet

### App Laadt Niet
```bash
# 1. Check service
ssh root@212.132.90.158 "systemctl status contract-checker-pilot"

# 2. Check logs voor errors
ssh root@212.132.90.158 "journalctl -u contract-checker-pilot -n 50"

# 3. Herstart service
ssh root@212.132.90.158 "systemctl restart contract-checker-pilot"
```

### 502 Bad Gateway
```bash
# Streamlit is down - herstart service
ssh root@212.132.90.158 "systemctl restart contract-checker-pilot"
```

### Database Error
```bash
# Check database verbinding
ssh root@212.132.90.158 "cd /opt/notifica/contract-checker && source venv/bin/activate && python3 -c 'from src.database.connection import get_db_connection; get_db_connection()'"
```

### Rollback naar Vorige Versie
```bash
# 1. SSH naar VPS4
ssh root@212.132.90.158

# 2. Stop service
systemctl stop contract-checker-pilot

# 3. Herstel backup (kies meest recente)
cd /opt/notifica
ls -lh contract-checker-backup-*
tar -xzf contract-checker-backup-YYYYMMDD-HHMMSS.tar.gz

# 4. Start service
systemctl start contract-checker-pilot
```

---

## Belangrijke URLs & Credentials

**Pilot URL:** https://wvc-pilot.notifica.nl

**WVC Login:**
- Username: `wvc_user`
- Password: `1r2UcLtiPNmOhS1`

**Server:**
- Host: `212.132.90.158` (VPS4)
- User: `root`
- SSH Key: `C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4`

---

## Monitoring

### Check Uptime
```bash
ssh root@212.132.90.158 "systemctl status contract-checker-pilot | grep Active"
```

### Check Logs voor Errors
```bash
ssh root@212.132.90.158 "journalctl -u contract-checker-pilot --since '1 hour ago' | grep -i error"
```

### Check Disk Space
```bash
ssh root@212.132.90.158 "df -h /opt/notifica"
```

---

## Handige Aliases (Optioneel)

Voeg toe aan je `~/.bashrc` of `~/.bash_profile`:

```bash
# SSH naar VPS4
alias vps4='ssh -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" root@212.132.90.158'

# Contract Checker logs
alias pilot-logs='ssh -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" root@212.132.90.158 "journalctl -u contract-checker-pilot -f"'

# Contract Checker herstart
alias pilot-restart='ssh -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" root@212.132.90.158 "systemctl restart contract-checker-pilot"'

# Deploy update
alias pilot-deploy='./deployment/deploy-update.sh'
```

Gebruik dan simpelweg:
```bash
vps4              # SSH naar server
pilot-logs        # Bekijk logs
pilot-restart     # Herstart service
pilot-deploy      # Deploy update
```
