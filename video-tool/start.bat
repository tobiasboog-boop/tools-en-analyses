@echo off
title Notifica Video Tool
cd /d "%~dp0"
color 0F

:: ============================================================
::  Notifica Video Tool — dubbelklik en klaar
::  Broncode mag op OneDrive staan; zware bestanden staan lokaal
:: ============================================================

echo.
echo  ========================================
echo    Notifica Video Tool
echo  ========================================
echo.

:: Lokale werkmap (venv, ffmpeg, temp, output — NIET op OneDrive)
set "NVT_LOCAL_DIR=%LOCALAPPDATA%\NotificaVideoTool"
if not exist "%NVT_LOCAL_DIR%" mkdir "%NVT_LOCAL_DIR%"

:: --- 1. Python ---
echo  [1/4] Python controleren...
python --version >nul 2>&1
if %errorlevel% equ 0 goto python_ok

echo         Niet gevonden - wordt automatisch geinstalleerd...
echo         Dit kan 1-2 minuten duren.
echo.
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent 2>nul
if %errorlevel% equ 0 goto python_installed

echo         Winget niet beschikbaar, directe download...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='%TEMP%\python-installer.exe'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile $f; Start-Process $f -ArgumentList '/quiet','InstallAllUsers=0','PrependPath=1' -Wait; Remove-Item $f -Force"

:python_installed
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo         Python geinstalleerd!
    goto python_ok
)
echo.
echo  [!] Python installatie mislukt. Herstart je PC en probeer opnieuw.
echo      Of installeer handmatig: https://www.python.org/downloads/
pause
exit /b 1

:python_ok
echo         OK

:: --- 2. Virtuele omgeving (lokaal, niet op OneDrive) ---
echo  [2/4] Virtuele omgeving controleren...
set "VENV_DIR=%NVT_LOCAL_DIR%\venv"
if exist "%VENV_DIR%\Scripts\activate.bat" goto venv_ok

echo         Wordt aangemaakt (eenmalig, ~30 sec)...
python -m venv "%VENV_DIR%"
call "%VENV_DIR%\Scripts\activate.bat"
echo         Pakketten installeren...
pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  [!] Pakketten installeren mislukt. Controleer je internetverbinding.
    pause
    exit /b 1
)
echo         Klaar!
goto venv_done

:venv_ok
call "%VENV_DIR%\Scripts\activate.bat"
echo         OK

:venv_done

:: --- 3. FFmpeg (lokaal, niet op OneDrive) ---
echo  [3/4] FFmpeg controleren...
set "FFMPEG_BIN=%NVT_LOCAL_DIR%\ffmpeg\bin"
if exist "%FFMPEG_BIN%\ffmpeg.exe" goto ffmpeg_ok

echo         Wordt gedownload (eenmalig, ~1-2 min)...
echo         Even geduld, dit is een groot bestand (~90 MB).
set "FFMPEG_PS=%NVT_LOCAL_DIR%\download_ffmpeg.ps1"
>"%FFMPEG_PS%" echo $ProgressPreference='SilentlyContinue'
>>"%FFMPEG_PS%" echo $bin = '%FFMPEG_BIN%'
>>"%FFMPEG_PS%" echo $dir = Split-Path $bin
>>"%FFMPEG_PS%" echo $zip = "$dir\ffmpeg.zip"
>>"%FFMPEG_PS%" echo $ext = "$dir\extract"
>>"%FFMPEG_PS%" echo New-Item -ItemType Directory -Path $bin -Force ^| Out-Null
>>"%FFMPEG_PS%" echo Write-Host '         Downloaden...'
>>"%FFMPEG_PS%" echo Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip
>>"%FFMPEG_PS%" echo Write-Host '         Uitpakken...'
>>"%FFMPEG_PS%" echo Expand-Archive -Path $zip -DestinationPath $ext -Force
>>"%FFMPEG_PS%" echo $sub = Get-ChildItem $ext -Directory ^| Select-Object -First 1
>>"%FFMPEG_PS%" echo Copy-Item -Path "$($sub.FullName)\bin\*" -Destination $bin -Force -Recurse
>>"%FFMPEG_PS%" echo Remove-Item $ext -Recurse -Force; Remove-Item $zip -Force

powershell -NoProfile -ExecutionPolicy Bypass -File "%FFMPEG_PS%"
del "%FFMPEG_PS%" >nul 2>&1

if not exist "%FFMPEG_BIN%\ffmpeg.exe" (
    echo.
    echo  [!] FFmpeg download mislukt. Controleer je internetverbinding.
    pause
    exit /b 1
)
echo         Klaar!
goto ffmpeg_done

:ffmpeg_ok
echo         OK

:ffmpeg_done

:: --- 4. Secrets ---
echo  [4/4] Configuratie controleren...
if exist ".streamlit\secrets.toml" goto secrets_ok
if not exist ".streamlit\secrets.toml.example" goto secrets_ok
copy ".streamlit\secrets.toml.example" ".streamlit\secrets.toml" >nul
echo         Secrets aangemaakt vanuit template.
goto secrets_done

:secrets_ok
echo         OK

:secrets_done

:: --- Starten ---
set "PORT=9501"

:: Sluit eventueel vorig proces op deze poort
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo  ----------------------------------------
echo    Alles klaar! App wordt gestart...
echo    http://localhost:%PORT%
echo    Sluit dit venster NIET.
echo  ----------------------------------------
echo.

:: Open browser na korte vertraging (streamlit heeft even nodig)
start "" /min powershell -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://localhost:%PORT%'"

streamlit run app.py --server.port %PORT%
pause
