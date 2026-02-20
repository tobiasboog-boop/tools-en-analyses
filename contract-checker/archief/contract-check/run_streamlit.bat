@echo off
REM Contract Checker - Streamlit App Launcher
REM Run on fixed port 8502, accessible from network

cd /d "%~dp0"
call venv\Scripts\activate.bat
streamlit run app.py --server.port 8502 --server.address 0.0.0.0 --server.headless true
