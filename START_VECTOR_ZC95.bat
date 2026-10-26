@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0Vector-ZC95.exe" goto python_source
"%~dp0Vector-ZC95.exe"
exit /b %errorlevel%
:python_source
python --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 or newer is required. Your existing Vector Python installation is suitable.
  pause
  exit /b 1
)
python server.py
if errorlevel 1 pause
