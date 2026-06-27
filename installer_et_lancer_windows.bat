@echo off
title Gestion Chantiers - Serveur
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ============================================================
    echo  Python n'est pas installe sur cet ordinateur.
    echo  Telechargez-le sur https://www.python.org/downloads/
    echo  (cochez bien "Add Python to PATH" lors de l'installation)
    echo ============================================================
    pause
    exit /b
)

echo Fermeture d'une eventuelle ancienne instance du serveur...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Gestion Chantiers*" >nul 2>nul

if not exist venv (
    echo Premiere installation, merci de patienter...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
    echo Mise a jour des dependances si necessaire...
    pip install -r requirements.txt >nul 2>nul
)

echo.
echo ============================================================
echo   GESTION CHANTIERS - le serveur demarre...
echo   Laissez cette fenetre ouverte pendant l'utilisation.
echo   Acces : http://localhost:5000
echo   (Astuce : faites Ctrl+F5 dans le navigateur pour forcer
echo    le rafraichissement si la page semble ancienne)
echo ============================================================
echo.
python app.py
pause
