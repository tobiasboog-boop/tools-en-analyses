@echo off
title Notifica Video Tool - Installatie
echo ========================================
echo   Notifica Video Tool - Installatie
echo ========================================
echo.

cd /d "%~dp0"

:: Stap 1: Python venv
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Python virtuele omgeving aanmaken...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo.
        echo [!] Python niet gevonden. Installeer Python 3.11+ van python.org
        echo     Zorg dat "Add Python to PATH" is aangevinkt bij installatie.
        echo.
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    echo [2/3] Dependencies installeren...
    pip install -q -r requirements.txt
) else (
    call venv\Scripts\activate.bat
    echo [1/3] Virtuele omgeving gevonden.
    echo [2/3] Dependencies controleren...
    pip install -q -r requirements.txt
)

:: Stap 2: FFmpeg downloaden als die er nog niet is
if not exist "ffmpeg\bin\ffmpeg.exe" (
    echo [3/3] FFmpeg downloaden...
    echo       Dit is eenmalig en kan 1-2 minuten duren.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0download_ffmpeg.ps1"

    if not exist "ffmpeg\bin\ffmpeg.exe" (
        echo.
        echo [!] FFmpeg downloaden mislukt.
        echo     Download handmatig van https://www.gyan.dev/ffmpeg/builds/
        echo     Pak "bin" map uit naar: %cd%\ffmpeg\bin\
        echo.
        pause
        exit /b 1
    )
) else (
    echo [3/3] FFmpeg al aanwezig.
)

:: Stap 3: Mappen aanmaken
if not exist "temp" mkdir temp

echo.
echo ========================================
echo   Installatie voltooid!
echo   Start de app met: start.bat
echo ========================================
