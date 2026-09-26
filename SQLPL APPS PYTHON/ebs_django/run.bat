@echo off
title EBS R12 Explorer (Django)
cd /d "%~dp0"

echo ============================================================
echo   EBS R12 Explorer - Django Edition
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12+
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYVER=%%i
echo [OK] Python !PYVER!
echo.

if not exist venv (
    echo [1/6] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

echo [2/6] Upgrading pip...
python -m pip install --quiet --upgrade pip

echo [3/6] Installing core dependencies...
pip install --quiet Django djangorestframework djangorestframework-simplejwt django-cors-headers waitress bcrypt python-dotenv cryptography oracledb
if errorlevel 1 (
    echo [ERROR] Core dependencies failed.
    pause
    exit /b 1
)
echo [OK] Core dependencies installed
echo.

echo [4/6] Applying database migrations...
python manage.py makemigrations api --noinput 2>nul
python manage.py migrate --noinput
if errorlevel 1 (
    echo [ERROR] Migrations failed.
    pause
    exit /b 1
)
echo [OK] Migrations applied
echo.
echo [5.5/6] Ensuring DB migrations for EBS connector...
python manage.py makemigrations api --noinput >nul 2>&1
python manage.py migrate --noinput

echo [5/6] Ensuring admin account exists...
python manage.py init_admin
echo.

echo [6/6] Starting server...
echo.
echo ============================================================
echo   Server URL : http://localhost:8000
echo   Admin Panel: http://localhost:8000/admin/
echo   Login      : ADMIN / ELKAZZAZ
echo ============================================================
echo.

python manage.py runserver 0.0.0.0:8000
pause