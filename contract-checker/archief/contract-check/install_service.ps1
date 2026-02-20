#Requires -RunAsAdministrator
# Contract Checker - Windows Service Installation Script
# Uses NSSM (Non-Sucking Service Manager) to run Streamlit as a service

$ServiceName = "ContractChecker"
$ServiceDisplayName = "Contract Checker Streamlit App"
$ServiceDescription = "WVC Contract Checker - Streamlit web application on port 8502"
$Port = 8502
$AppPath = $PSScriptRoot

Write-Host "=== Contract Checker Service Installer ===" -ForegroundColor Cyan
Write-Host ""

# Check if NSSM is installed
$nssmPath = Join-Path $AppPath "nssm\nssm.exe"
$nssm = Get-Command nssm -ErrorAction SilentlyContinue

if (-not $nssm -and -not (Test-Path $nssmPath)) {
    Write-Host "NSSM not found. Downloading..." -ForegroundColor Yellow

    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $nssmZip = Join-Path $env:TEMP "nssm.zip"
    $nssmExtract = Join-Path $env:TEMP "nssm-extract"

    try {
        # Download NSSM
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing

        # Extract
        if (Test-Path $nssmExtract) { Remove-Item $nssmExtract -Recurse -Force }
        Expand-Archive -Path $nssmZip -DestinationPath $nssmExtract -Force

        # Copy to project folder
        $nssmDir = Join-Path $AppPath "nssm"
        if (-not (Test-Path $nssmDir)) { New-Item -ItemType Directory -Path $nssmDir | Out-Null }

        Copy-Item (Join-Path $nssmExtract "nssm-2.24\win64\nssm.exe") $nssmDir -Force

        # Cleanup
        Remove-Item $nssmZip -Force
        Remove-Item $nssmExtract -Recurse -Force

        Write-Host "NSSM downloaded to: $nssmDir" -ForegroundColor Green
    }
    catch {
        Write-Host "ERROR: Could not download NSSM: $_" -ForegroundColor Red
        Write-Host "Please download manually from https://nssm.cc/release/nssm-2.24.zip" -ForegroundColor Yellow
        exit 1
    }
}

# Set nssm path
if (Test-Path $nssmPath) {
    $nssm = $nssmPath
} else {
    $nssm = "nssm"
}

Write-Host "NSSM found at: $nssm" -ForegroundColor Green

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Service '$ServiceName' already exists. Stopping and removing..." -ForegroundColor Yellow
    & $nssm stop $ServiceName
    & $nssm remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

# Install the service
Write-Host ""
Write-Host "Installing service..." -ForegroundColor Cyan

$pythonExe = Join-Path $AppPath "venv\Scripts\python.exe"
$streamlitExe = Join-Path $AppPath "venv\Scripts\streamlit.exe"
$appFile = Join-Path $AppPath "app.py"

if (-not (Test-Path $streamlitExe)) {
    Write-Host "ERROR: Streamlit not found at $streamlitExe" -ForegroundColor Red
    Write-Host "Make sure the virtual environment is set up correctly." -ForegroundColor Yellow
    exit 1
}

# Install service with NSSM
& $nssm install $ServiceName $streamlitExe
& $nssm set $ServiceName AppParameters "run `"$appFile`" --server.port $Port --server.address 0.0.0.0 --server.headless true"
& $nssm set $ServiceName AppDirectory $AppPath
& $nssm set $ServiceName DisplayName $ServiceDisplayName
& $nssm set $ServiceName Description $ServiceDescription
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm set $ServiceName AppStdout (Join-Path $AppPath "logs\service_stdout.log")
& $nssm set $ServiceName AppStderr (Join-Path $AppPath "logs\service_stderr.log")
& $nssm set $ServiceName AppRotateFiles 1
& $nssm set $ServiceName AppRotateBytes 1048576

# Create logs directory
$logsDir = Join-Path $AppPath "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
    Write-Host "Created logs directory: $logsDir" -ForegroundColor Green
}

Write-Host "Service installed successfully!" -ForegroundColor Green

# Configure firewall
Write-Host ""
Write-Host "Configuring Windows Firewall..." -ForegroundColor Cyan

$firewallRuleName = "Contract Checker Streamlit (TCP $Port)"

# Remove existing rule if present
$existingRule = Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Remove-NetFirewallRule -DisplayName $firewallRuleName
    Write-Host "Removed existing firewall rule." -ForegroundColor Yellow
}

# Add new firewall rule
New-NetFirewallRule -DisplayName $firewallRuleName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $Port `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Allow inbound connections to Contract Checker Streamlit app on port $Port"

Write-Host "Firewall rule added for port $Port (Domain & Private networks)" -ForegroundColor Green

# Start the service
Write-Host ""
Write-Host "Starting service..." -ForegroundColor Cyan
& $nssm start $ServiceName

Start-Sleep -Seconds 3

# Check service status
$service = Get-Service -Name $ServiceName
if ($service.Status -eq "Running") {
    Write-Host ""
    Write-Host "=== SUCCESS ===" -ForegroundColor Green
    Write-Host "Service '$ServiceName' is running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Access the app at:" -ForegroundColor Cyan
    Write-Host "  Local:   http://localhost:$Port" -ForegroundColor White
    Write-Host "  Network: http://$($env:COMPUTERNAME):$Port" -ForegroundColor White
    Write-Host ""
    Write-Host "Service management commands:" -ForegroundColor Cyan
    Write-Host "  Stop:    .\nssm\nssm.exe stop $ServiceName" -ForegroundColor White
    Write-Host "  Start:   .\nssm\nssm.exe start $ServiceName" -ForegroundColor White
    Write-Host "  Restart: .\nssm\nssm.exe restart $ServiceName" -ForegroundColor White
    Write-Host "  Remove:  .\nssm\nssm.exe remove $ServiceName confirm" -ForegroundColor White
} else {
    Write-Host "WARNING: Service may not have started correctly. Status: $($service.Status)" -ForegroundColor Yellow
    Write-Host "Check logs at: $logsDir" -ForegroundColor Yellow
}
