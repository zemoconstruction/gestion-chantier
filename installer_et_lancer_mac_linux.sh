#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "============================================================"
    echo " Python 3 n'est pas installé sur cet ordinateur."
    echo " Installez-le depuis https://www.python.org/downloads/"
    echo "============================================================"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Première installation, merci de patienter..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "============================================================"
echo "  GESTION CHANTIERS - le serveur démarre..."
echo "  Laissez ce terminal ouvert pendant l'utilisation."
echo "============================================================"
echo ""
python3 app.py
