@echo off
setlocal
cd /d "%~dp0.."

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found, creating it...
    python -m venv venv
)
call venv\Scripts\activate.bat
if not exist "venv\Lib\site-packages\fastapi" (
    echo Dependencies not installed, installing them...
    pip install -r requirements.txt
)

python scripts\set_password.py %*
