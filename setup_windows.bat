@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "BASE_PYTHON=python"
if exist "C:\Python314\python.exe" set "BASE_PYTHON=C:\Python314\python.exe"
"%BASE_PYTHON%" --version
if errorlevel 1 goto FAIL
if not exist ".venv\Scripts\python.exe" "%BASE_PYTHON%" -m venv .venv
if errorlevel 1 goto FAIL
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto FAIL
echo Setup complete. Double-click run_app.bat.
pause
exit /b 0
:FAIL
echo Setup failed. Check the error above. Python 3.11 or newer and internet access are required.
pause
exit /b 1
