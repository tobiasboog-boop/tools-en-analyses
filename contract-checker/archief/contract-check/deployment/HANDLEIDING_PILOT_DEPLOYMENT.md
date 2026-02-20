# Complete Handleiding: Contract Checker Pilot Deployment

## Wat je hebt ontvangen

Je hebt 3 bestanden gedownload:

| Bestand | Wat het is |
|---------|------------|
| `wvc-pilot.nginx.conf` | Nginx configuratie - vertelt Nginx hoe verkeer te routeren |
| `contract-checker-pilot.service` | Systemd service - zorgt dat Streamlit automatisch draait |
| `deploy-pilot.sh` | Hulpscript - checklist van alle stappen |

---

## Stap-voor-stap handleiding

### STAP 1: DNS instellen in Cloudflare (5 minuten)

1. **Login op Cloudflare** → https://dash.cloudflare.com

2. **Selecteer domein** → `notifica.nl`

3. **Ga naar DNS** → Klik op "DNS" in het linkermenu

4. **Voeg record toe** → Klik op "Add record"
   ```
   Type:    A
   Name:    wvc-pilot
   IPv4:    [IP adres van VPS4]
   Proxy:   Oranje wolk AAN (Proxied)
   TTL:     Auto
   ```

5. **Klik "Save"**

6. **Wacht 1-5 minuten** tot DNS is gepropageerd

**Check:** Open terminal en run:
```bash
ping wvc-pilot.notifica.nl
```
Als je een IP terugkrijgt, werkt DNS.

---

### STAP 2: Bestanden naar VPS4 kopiëren (5 minuten)

**Vanaf je Windows PC (PowerShell):**

```powershell
# Ga naar waar je de bestanden hebt gedownload
cd C:\Users\JOUW_NAAM\Downloads

# Kopieer naar VPS4 (pas IP/hostname aan)
scp wvc-pilot.nginx.conf root@VPS4_IP:/etc/nginx/sites-available/wvc-pilot.conf
scp contract-checker-pilot.service root@VPS4_IP:/etc/systemd/system/
scp deploy-pilot.sh root@VPS4_IP:/opt/notifica/
```

**Of via WinSCP:**
1. Open WinSCP
2. Connect naar VPS4
3. Sleep bestanden naar juiste mappen:
   - `wvc-pilot.nginx.conf` → `/etc/nginx/sites-available/wvc-pilot.conf`
   - `contract-checker-pilot.service` → `/etc/systemd/system/`
   - `deploy-pilot.sh` → `/opt/notifica/`

---

### STAP 3: SSH naar VPS4 (rest van de stappen)

```bash
ssh root@VPS4_IP
```

---

### STAP 4: Contract Checker code deployen (10 minuten)

```bash
# Maak directory
mkdir -p /opt/notifica
cd /opt/notifica

# Clone je repository (of kopieer handmatig)
# OPTIE A: Via git (als je repo hebt)
git clone https://github.com/JOUW_ORG/contract-check.git contract-checker

# OPTIE B: Handmatig kopiëren vanaf je PC
# Gebruik WinSCP om contract-check folder te kopiëren naar /opt/notifica/contract-checker

# Ga naar de folder
cd /opt/notifica/contract-checker

# Maak virtual environment
python3 -m venv venv

# Activeer venv
source venv/bin/activate

# Installeer dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

### STAP 5: Environment variables instellen (5 minuten)

**Open de systemd service file:**
```bash
nano /etc/systemd/system/contract-checker-pilot.service
```

**Pas deze regels aan:**
```ini
# Database connectie - vraag Mark voor juiste credentials
Environment="DATABASE_URL=postgresql://username:password@10.0.0.X:5432/dwh_1210"

# Anthropic API key - uit je .env of Anthropic dashboard
Environment="ANTHROPIC_API_KEY=sk-ant-api03-..."
```

**Sla op:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### STAP 6: Nginx configureren (5 minuten)

```bash
# Maak symlink om config te activeren
ln -s /etc/nginx/sites-available/wvc-pilot.conf /etc/nginx/sites-enabled/

# Maak wachtwoord voor WVC
# Je wordt gevraagd om een wachtwoord in te voeren
htpasswd -c /etc/nginx/.htpasswd-wvc wvc_user

# Test nginx configuratie
nginx -t

# Als "syntax is ok" → reload nginx
systemctl reload nginx
```

**Onthoud het wachtwoord!** Dit geef je aan WVC.

---

### STAP 7: Services starten (2 minuten)

```bash
# Herlaad systemd (zodat hij nieuwe service ziet)
systemctl daemon-reload

# Enable service (start automatisch bij reboot)
systemctl enable contract-checker-pilot

# Start de service
systemctl start contract-checker-pilot

# Check of hij draait
systemctl status contract-checker-pilot
```

**Je moet zien:** `Active: active (running)`

**Als er errors zijn:**
```bash
# Bekijk logs
journalctl -u contract-checker-pilot -f
```

---

### STAP 8: SSL certificaat installeren (2 minuten)

```bash
# Vraag certificaat aan (certbot regelt alles)
certbot --nginx -d wvc-pilot.notifica.nl
```

Certbot vraagt:
- Email: vul je email in
- Terms: `Y`
- Redirect HTTP to HTTPS: `2` (Yes)

---

### STAP 9: Testen! (2 minuten)

1. **Open browser** → `https://wvc-pilot.notifica.nl`

2. **Login popup verschijnt:**
   - Username: `wvc_user`
   - Password: [wat je in stap 6 hebt ingesteld]

3. **Streamlit app moet laden**

---

## Troubleshooting

### "502 Bad Gateway"
Streamlit draait niet:
```bash
systemctl status contract-checker-pilot
journalctl -u contract-checker-pilot -n 50
```

### "Connection refused"
Check of poort 8501 luistert:
```bash
ss -tlnp | grep 8501
```

### "Site not found"
DNS nog niet gepropageerd, wacht 5 minuten of check Cloudflare.

### Wachtwoord vergeten
```bash
# Maak nieuw wachtwoord
htpasswd /etc/nginx/.htpasswd-wvc wvc_user
```

---

## Samenvatting commando's

Alles achter elkaar (na bestanden zijn gekopieerd):

```bash
# Op VPS4
cd /opt/notifica
git clone [REPO_URL] contract-checker
cd contract-checker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Pas environment variables aan
nano /etc/systemd/system/contract-checker-pilot.service

# Nginx
ln -s /etc/nginx/sites-available/wvc-pilot.conf /etc/nginx/sites-enabled/
htpasswd -c /etc/nginx/.htpasswd-wvc wvc_user
nginx -t && systemctl reload nginx

# Start service
systemctl daemon-reload
systemctl enable --now contract-checker-pilot

# SSL
certbot --nginx -d wvc-pilot.notifica.nl
```

---

## Wat je aan WVC geeft

Na succesvolle deployment, stuur naar WVC:

```
Beste [naam],

De Contract Checker pilot staat klaar.

URL: https://wvc-pilot.notifica.nl
Gebruikersnaam: wvc_user
Wachtwoord: [wachtwoord]

Laat me weten als je vragen hebt!

Groet,
Mark
```

---

## Later: Uitfaseren

Wanneer de React app klaar is met de werkbon checker module:

1. Verander nginx config naar redirect:
```nginx
server {
    server_name wvc-pilot.notifica.nl;
    return 301 https://app.notifica.nl/apps/werkbon-checker;
}
```

2. Stop Streamlit service:
```bash
systemctl disable --now contract-checker-pilot
```

3. Informeer WVC over nieuwe URL
