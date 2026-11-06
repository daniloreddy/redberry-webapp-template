@echo off
setlocal
cd /d "%~dp0.."

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found, creating it...
    python -m venv venv
)
call venv\Scripts\activate.bat
if not exist "venv\Lib\site-packages\ruff" (
    echo Dependencies not installed, installing them...
    pip install -r requirements.dev.txt
)

echo === ruff ===
ruff check .
if errorlevel 1 exit /b 1

echo === mypy ===
mypy app
if errorlevel 1 exit /b 1

echo === pytest ===
pytest
if errorlevel 1 exit /b 1

echo All checks passed.
