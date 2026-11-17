@echo off
rem Print a random bearer token for API_TOKENS in .env (32 bytes, URL-safe).
setlocal
cd /d "%~dp0.."
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
"%PY%" -c "import secrets; print(secrets.token_urlsafe(32))"
