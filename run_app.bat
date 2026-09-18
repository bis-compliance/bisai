@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BIS AI 7.1 - Developed by UIBox Studio
if exist ".venv\Scripts\python.exe" (
  set "APP_PYTHON=.venv\Scripts\python.exe"
  goto CHECK
)
if exist "C:\Python314\python.exe" (
  set "APP_PYTHON=C:\Python314\python.exe"
  goto CHECK
)
where python >nul 2>&1
if not errorlevel 1 (
  set "APP_PYTHON=python"
  goto CHECK
)
echo Python was not found. Install Python 3.11 or newer, then run setup_windows.bat.
pause
exit /b 1
:CHECK
"%APP_PYTHON%" -c "import streamlit,pandas,numpy,openpyxl,xlrd,dns.resolver"
if errorlevel 1 (
  echo Dependencies are missing. Run setup_windows.bat once, then try again.
  pause
  exit /b 1
)
echo Starting BIS AI. Keep this window open.
"%APP_PYTHON%" -m streamlit run app.py --server.address 127.0.0.1
if errorlevel 1 pause
