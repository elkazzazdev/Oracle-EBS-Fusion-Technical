#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "============================================================"
echo "  EBS R12 Explorer - Django Edition"
echo "============================================================"
echo

python3 --version || { echo "[ERROR] Python 3 not found"; exit 1; }
echo

if [ ! -d "venv" ]; then
    echo "[1/6] Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "[OK] Virtual environment activated"
echo

echo "[2/6] Upgrading pip..."
pip install --quiet --upgrade pip
echo "[OK] pip upgraded"
echo

echo "[3/6] Installing dependencies..."
pip install --quiet -r requirements.txt
echo "[OK] Dependencies installed"
echo

echo "[4/6] Applying database migrations..."
python manage.py makemigrations --noinput 2>/dev/null
python manage.py migrate --noinput
echo "[OK] Migrations applied"
echo

echo "[5/6] Ensuring admin account exists..."
python manage.py init_admin
echo

echo "[6/6] Starting server..."
echo
echo "============================================================"
echo "  Server URL : http://localhost:8000"
echo "  Admin Panel: http://localhost:8000/admin/"
echo "  Login      : ADMIN / ELKAZZAZ"
echo "============================================================"
echo

python manage.py runserver 0.0.0.0:8000


