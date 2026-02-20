# Beheer Handleiding: Contract Checker Pilot (WVC)

## Overzicht

De Contract Checker pilot draait op VPS4 en is bereikbaar via [https://wvc-pilot.notifica.nl](https://wvc-pilot.notifica.nl)

**Server:** VPS4 (212.132.90.158)
**Locatie:** `/opt/notifica/contract-checker`
**Service:** `contract-checker-pilot.service`
**Port:** 8501 (intern), 443 (extern via nginx)

---

## Dagelijks Beheer

### Service Status Checken

```bash
# SSH naar VPS4
ssh root@212.132.90.158

# Check of service draait
systemctl status contract-checker-pilot

# Logs bekijken (live)
journalctl -u contract-checker-pilot -f

# Laatste 50 log regels
journalctl -u contract-checker-pilot -n 50
```

### Service Beheren

```bash
# Service herstarten (na problemen)
systemctl restart contract-checker-pilot

# Service stoppen
systemctl stop contract-checker-pilot

# Service starten
systemctl start contract-checker-pilot

# Check of Streamlit op poort 8501 luistert
ss -tlnp | grep 8501
```

### Nginx Beheren

```bash
# Nginx status
systemctl status nginx

# Nginx config testen
nginx -t

# Nginx herstarten
systemctl restart nginx

# Nginx logs bekijken
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

---

## Updates Deployen (Releases)

### Optie 1: Automatisch Deploy Script (Aanbevolen)

Gebruik het `deploy-update.sh` script vanaf je Windows PC:

```bash
# Vanaf de contract-check directory op je PC
./deployment/deploy-update.sh
```

Dit script:
1. Maakt een backup van de huidige versie op VPS4
2. Kopieert nieuwe code naar VPS4
3. Herstart de service
4. Toont de logs

### Optie 2: Handmatig Deployen

**Stap 1: Code voorbereiden op je PC**
```bash
# Zorg dat je lokaal getest hebt
streamlit run Home.py

# Check welke bestanden veranderd zijn
git status
```

**Stap 2: Code kopiëren naar VPS4**
```bash
# Belangrijke Python bestanden
scp -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" *.py requirements.txt root@212.132.90.158:/opt/notifica/contract-checker/

# Pages folder
scp -r -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" pages root@212.132.90.158:/opt/notifica/contract-checker/

# Src folder
scp -r -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" src root@212.132.90.158:/opt/notifica/contract-checker/

# SQL scripts (indien nodig)
scp -r -i "C:/Users/markh/OneDrive - Notifica B.V/Persoonlijk/putty/id_rsa_vps4" sql root@212.132.90.158:/opt/notifica/contract-checker/
```

**Stap 3: Dependencies updaten (indien requirements.txt gewijzigd)**
```bash
ssh root@212.132.90.158
cd /opt/notifica/contract-checker
source venv/bin/activate
pip install -r requirements.txt
```

**Stap 4: Service herstarten**
```bash
systemctl restart contract-checker-pilot

# Check of het werkt
systemctl status contract-checker-pilot
journalctl -u contract-checker-pilot -n 20
```

**Stap 5: Test in browser**
- Open [https://wvc-pilot.notifica.nl](https://wvc-pilot.notifica.nl)
- Login met WVC credentials
- Test de nieuwe functionaliteit

---

## Versie Beheer met Git Tags

Om releases te tracken, gebruik Git tags:

```bash
# Maak een nieuwe versie/release tag
git tag -a v1.0.1 -m "Fix: Bug in contract classification"
git push origin v1.0.1

# Bekijk alle releases
git tag

# Deploy een specifieke versie
git checkout v1.0.1
./deployment/deploy-update.sh
git checkout main
```

**Aanbevolen versie nummering:**
- `v1.0.0` - Eerste pilot release
- `v1.0.1` - Kleine bug fix
- `v1.1.0` - Nieuwe feature
- `v2.0.0` - Major change

---

## Backup & Rollback

### Backup Maken

Het deploy script maakt automatisch een backup, maar je kunt ook handmatig:

```bash
ssh root@212.132.90.158

# Maak backup van huidige versie
cd /opt/notifica
tar -czf contract-checker-backup-$(date +%Y%m%d-%H%M%S).tar.gz contract-checker/
```

### Rollback naar Vorige Versie

```bash
ssh root@212.132.90.158
cd /opt/notifica

# Stop de service
systemctl stop contract-checker-pilot

# Herstel backup
tar -xzf contract-checker-backup-YYYYMMDD-HHMMSS.tar.gz

# Start service
systemctl start contract-checker-pilot
```

---

## SSL Certificaat Beheer

SSL certificaat wordt automatisch verlengd via acme.sh cron job.

### Handmatig Verlengen

```bash
ssh root@212.132.90.158
/root/.acme.sh/acme.sh --renew -d wvc-pilot.notifica.nl --ecc --force
systemctl reload nginx
```

### Certificaat Info Bekijken

```bash
/root/.acme.sh/acme.sh --info -d wvc-pilot.notifica.nl --ecc
```

---

## Troubleshooting

### Service Start Niet

```bash
# Check logs voor error
journalctl -u contract-checker-pilot -n 50 --no-pager

# Veelvoorkomende oorzaken:
# 1. Database connectie probleem
#    → Check DATABASE_URL in /etc/systemd/system/contract-checker-pilot.service
# 2. Python dependencies ontbreken
#    → cd /opt/notifica/contract-checker && source venv/bin/activate && pip install -r requirements.txt
# 3. Poort 8501 al in gebruik
#    → ss -tlnp | grep 8501 && kill <PID>
```

### "502 Bad Gateway" in Browser

Streamlit draait niet:
```bash
systemctl status contract-checker-pilot
# Als "inactive (dead)" → start de service
systemctl start contract-checker-pilot
```

### Database Verbinding Fout

```bash
# Test database verbinding vanaf VPS4
ssh root@212.132.90.158
cd /opt/notifica/contract-checker
source venv/bin/activate
python3 -c "
from src.database.connection import get_db_connection
try:
    conn = get_db_connection()
    print('✓ Database verbinding werkt!')
    conn.close()
except Exception as e:
    print(f'✗ Database fout: {e}')
"
```

### Hoge Memory/CPU Gebruik

```bash
# Check resource gebruik
htop

# Als Streamlit te veel memory gebruikt:
systemctl restart contract-checker-pilot
```

---

## Monitoring & Performance

### Disk Space Checken

```bash
df -h /opt/notifica
```

### Log Rotatie

Logs worden automatisch geroteerd door systemd journal. Handmatig:

```bash
# Oude logs opschonen (ouder dan 7 dagen)
journalctl --vacuum-time=7d
```

### Uptime Checken

```bash
# Check hoe lang service draait
systemctl status contract-checker-pilot | grep Active

# Check VPS4 uptime
uptime
```

---

## Contact & Escalatie

**Bij problemen:**
1. Check de logs: `journalctl -u contract-checker-pilot -f`
2. Herstart de service: `systemctl restart contract-checker-pilot`
3. Check database verbinding
4. Als het niet werkt: rollback naar vorige versie

**WVC Contact:**
- URL: https://wvc-pilot.notifica.nl
- Username: `wvc_user`
- Password: `1r2UcLtiPNmOhS1`

---

## Belangrijke Bestanden & Locaties

| Locatie | Beschrijving |
|---------|--------------|
| `/opt/notifica/contract-checker/` | Applicatie code |
| `/opt/notifica/contract-checker/venv/` | Python virtual environment |
| `/etc/systemd/system/contract-checker-pilot.service` | Systemd service configuratie |
| `/etc/nginx/sites-available/wvc-pilot.conf` | Nginx configuratie |
| `/etc/nginx/.htpasswd-wvc` | HTTP basic auth wachtwoord |
| `/etc/nginx/ssl/wvc-pilot.notifica.nl.*` | SSL certificaten |
| `/root/.acme.sh/` | SSL certificaat beheer |

---

## Uitfaseren Pilot

Wanneer de React app klaar is:

```bash
# 1. Stop de Streamlit service
systemctl stop contract-checker-pilot
systemctl disable contract-checker-pilot

# 2. Update nginx naar redirect
nano /etc/nginx/sites-available/wvc-pilot.conf
# Vervang inhoud door redirect naar app.notifica.nl/apps/werkbon-checker

# 3. Test en reload nginx
nginx -t && systemctl reload nginx

# 4. Informeer WVC over nieuwe URL
```
