# Deploy Script voor Contract Checker Pilot Updates
# Gebruik: .\deployment\deploy-update.ps1

Write-Host "=== Contract Checker Pilot Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Configuratie uit .env laden
$envPath = ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "ERROR: .env file niet gevonden!" -ForegroundColor Red
    exit 1
}

# Parse .env voor SSH credentials
$envContent = Get-Content $envPath
$VPS4_HOST = ($envContent | Select-String "VPS4_HOST=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value }).Trim()
$VPS4_USER = ($envContent | Select-String "VPS4_USER=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value }).Trim()
$VPS4_SSH_KEY = ($envContent | Select-String "VPS4_SSH_KEY_PATH=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value }).Trim()

if (-not $VPS4_HOST -or -not $VPS4_USER -or -not $VPS4_SSH_KEY) {
    Write-Host "ERROR: VPS4 credentials niet gevonden in .env!" -ForegroundColor Red
    exit 1
}

Write-Host "Target: $VPS4_USER@$VPS4_HOST" -ForegroundColor Green
Write-Host ""

# Bevestiging vragen
$confirm = Read-Host "Wil je de huidige code deployen naar VPS4? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Deployment geannuleerd." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "[1/5] Backup maken op VPS4..." -ForegroundColor Cyan
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
ssh -i $VPS4_SSH_KEY "$VPS4_USER@$VPS4_HOST" "cd /opt/notifica && tar -czf contract-checker-backup-$timestamp.tar.gz contract-checker/ && echo 'Backup: contract-checker-backup-$timestamp.tar.gz'"

Write-Host ""
Write-Host "[2/5] Python bestanden kopieren..." -ForegroundColor Cyan
scp -i $VPS4_SSH_KEY *.py requirements.txt "$VPS4_USER@$VPS4_HOST:/opt/notifica/contract-checker/"

Write-Host ""
Write-Host "[3/5] Folders kopieren (pages, src, sql, .streamlit)..." -ForegroundColor Cyan
scp -r -i $VPS4_SSH_KEY pages src sql .streamlit "$VPS4_USER@$VPS4_HOST:/opt/notifica/contract-checker/"

Write-Host ""
Write-Host "[4/5] Dependencies updaten (indien nodig)..." -ForegroundColor Cyan
ssh -i $VPS4_SSH_KEY "$VPS4_USER@$VPS4_HOST" "cd /opt/notifica/contract-checker && source venv/bin/activate && pip install -r requirements.txt -q"

Write-Host ""
Write-Host "[5/5] Service herstarten..." -ForegroundColor Cyan
ssh -i $VPS4_SSH_KEY "$VPS4_USER@$VPS4_HOST" "systemctl restart contract-checker-pilot && sleep 3 && systemctl status contract-checker-pilot --no-pager"

Write-Host ""
Write-Host "=== Deployment Voltooid! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Test de applicatie: https://wvc-pilot.notifica.nl" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs bekijken:" -ForegroundColor Yellow
Write-Host "  ssh -i `"$VPS4_SSH_KEY`" $VPS4_USER@$VPS4_HOST 'journalctl -u contract-checker-pilot -f'" -ForegroundColor Gray
Write-Host ""

# Optie om logs te bekijken
$viewLogs = Read-Host "Wil je de logs bekijken? (y/n)"
if ($viewLogs -eq "y") {
    Write-Host ""
    Write-Host "Logs (Ctrl+C om te stoppen):" -ForegroundColor Cyan
    ssh -i $VPS4_SSH_KEY "$VPS4_USER@$VPS4_HOST" "journalctl -u contract-checker-pilot -f"
}
