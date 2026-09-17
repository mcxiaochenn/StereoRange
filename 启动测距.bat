@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found. See README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py %*
exit /b %errorlevel%
