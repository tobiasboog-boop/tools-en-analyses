#!/bin/bash
# ============================================================================
# Deploy Contract Checker Pilot naar VPS4
# ============================================================================
#
# Dit script voer je uit OP VPS4 (niet lokaal)
#
# Gebruik:
#   1. SSH naar VPS4
#   2. Download/kopieer dit script
#   3. chmod +x deploy-pilot.sh
#   4. ./deploy-pilot.sh
#
# ============================================================================

set -e  # Stop bij errors

echo "=========================================="
echo "Contract Checker Pilot Deployment"
echo "=========================================="

# === CONFIGURATIE ===
REPO_URL="https://github.com/JOUW-REPO/contract-check.git"  # PAS AAN
INSTALL_DIR="/opt/notifica/contract-checker"
DOMAIN="wvc-pilot.notifica.nl"

# === STAP 1: Directory aanmaken ===
echo ""
echo "[1/7] Directory aanmaken..."
mkdir -p /opt/notifica
cd /opt/notifica

# === STAP 2: Code ophalen ===
echo ""
echo "[2/7] Code ophalen..."
if [ -d "$INSTALL_DIR" ]; then
    echo "Directory bestaat al, git pull..."
    cd $INSTALL_DIR
    git pull
else
    echo "Cloning repository..."
    git clone $REPO_URL contract-checker
    cd $INSTALL_DIR
fi

# === STAP 3: Virtual environment ===
echo ""
echo "[3/7] Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# === STAP 4: Environment variables ===
echo ""
echo "[4/7] Environment configuratie..."
if [ ! -f ".env" ]; then
    echo "WAARSCHUWING: .env bestand ontbreekt!"
    echo "Maak .env aan met:"
    echo "  DATABASE_URL=postgresql://..."
    echo "  ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    echo "Of pas de systemd service aan met de juiste environment variables."
fi

# === STAP 5: Systemd service ===
echo ""
echo "[5/7] Systemd service installeren..."
if [ -f "/etc/systemd/system/contract-checker-pilot.service" ]; then
    echo "Service bestaat al, controleer environment variables!"
else
    echo "ACTIE NODIG: Kopieer contract-checker-pilot.service naar /etc/systemd/system/"
    echo "en pas de environment variables aan."
fi

# === STAP 6: Nginx configuratie ===
echo ""
echo "[6/7] Nginx configuratie..."
if [ -f "/etc/nginx/sites-enabled/wvc-pilot.conf" ]; then
    echo "Nginx config bestaat al."
else
    echo "ACTIE NODIG:"
    echo "  1. Kopieer wvc-pilot.nginx.conf naar /etc/nginx/sites-available/wvc-pilot.conf"
    echo "  2. ln -s /etc/nginx/sites-available/wvc-pilot.conf /etc/nginx/sites-enabled/"
    echo "  3. htpasswd -c /etc/nginx/.htpasswd-wvc wvc_user"
    echo "  4. nginx -t && systemctl reload nginx"
fi

# === STAP 7: SSL certificaat ===
echo ""
echo "[7/7] SSL certificaat..."
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "SSL certificaat bestaat al."
else
    echo "ACTIE NODIG (na DNS configuratie):"
    echo "  certbot --nginx -d $DOMAIN"
fi

# === SAMENVATTING ===
echo ""
echo "=========================================="
echo "Deployment samenvatting"
echo "=========================================="
echo ""
echo "Code locatie:     $INSTALL_DIR"
echo "Domain:           $DOMAIN"
echo ""
echo "Handmatige stappen:"
echo "  1. Pas environment variables aan in systemd service"
echo "  2. systemctl daemon-reload"
echo "  3. systemctl enable --now contract-checker-pilot"
echo "  4. Configureer DNS in Cloudflare"
echo "  5. certbot --nginx -d $DOMAIN"
echo "  6. Test: https://$DOMAIN"
echo ""
echo "Logs bekijken:"
echo "  journalctl -u contract-checker-pilot -f"
echo ""
echo "=========================================="
