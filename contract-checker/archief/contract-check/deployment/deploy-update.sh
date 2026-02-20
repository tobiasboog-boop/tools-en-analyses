#!/bin/bash
# Deploy Script voor Contract Checker Pilot Updates
# Gebruik: ./deployment/deploy-update.sh

set -e  # Stop bij errors

echo "=== Contract Checker Pilot Deployment ==="
echo ""

# Configuratie uit .env laden
if [ ! -f .env ]; then
    echo "ERROR: .env file niet gevonden!"
    exit 1
fi

# Parse .env voor SSH credentials
export $(grep -v '^#' .env | grep VPS4_ | xargs)

if [ -z "$VPS4_HOST" ] || [ -z "$VPS4_USER" ] || [ -z "$VPS4_SSH_KEY_PATH" ]; then
    echo "ERROR: VPS4 credentials niet gevonden in .env!"
    exit 1
fi

SSH_CMD="ssh -i \"$VPS4_SSH_KEY_PATH\" $VPS4_USER@$VPS4_HOST"
SCP_CMD="scp -i \"$VPS4_SSH_KEY_PATH\""

echo "Target: $VPS4_USER@$VPS4_HOST"
echo ""

# Bevestiging vragen
read -p "Wil je de huidige code deployen naar VPS4? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment geannuleerd."
    exit 0
fi

echo ""
echo "[1/5] Backup maken op VPS4..."
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
eval $SSH_CMD "cd /opt/notifica && tar -czf contract-checker-backup-$TIMESTAMP.tar.gz contract-checker/ && echo 'Backup: contract-checker-backup-$TIMESTAMP.tar.gz'"

echo ""
echo "[2/5] Python bestanden kopiëren..."
eval $SCP_CMD *.py requirements.txt $VPS4_USER@$VPS4_HOST:/opt/notifica/contract-checker/

echo ""
echo "[3/5] Folders kopiëren (pages, src, sql, .streamlit)..."
eval $SCP_CMD -r pages src sql .streamlit $VPS4_USER@$VPS4_HOST:/opt/notifica/contract-checker/

echo ""
echo "[4/5] Dependencies updaten (indien nodig)..."
eval $SSH_CMD "cd /opt/notifica/contract-checker && source venv/bin/activate && pip install -r requirements.txt -q"

echo ""
echo "[5/5] Service herstarten..."
eval $SSH_CMD "systemctl restart contract-checker-pilot && sleep 3 && systemctl status contract-checker-pilot --no-pager"

echo ""
echo "=== Deployment Voltooid! ==="
echo ""
echo "Test de applicatie: https://wvc-pilot.notifica.nl"
echo ""
echo "Logs bekijken:"
echo "  $SSH_CMD 'journalctl -u contract-checker-pilot -f'"
echo ""

# Optie om logs te bekijken
read -p "Wil je de logs bekijken? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Logs (Ctrl+C om te stoppen):"
    eval $SSH_CMD "journalctl -u contract-checker-pilot -f"
fi
