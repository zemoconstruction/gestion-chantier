@echo off
title Fabrication du logiciel GestionChantiers.exe
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ============================================================
    echo  Python n'est pas installe sur cet ordinateur.
    echo  Telechargez-le sur https://www.python.org/downloads/
    echo  Cochez bien "Add Python to PATH" pendant l'installation,
    echo  puis relancez ce fichier.
    echo ============================================================
    pause
    exit /b
)

echo ============================================================
echo  Nettoyage des anciennes fabrications (pour forcer la mise a jour)...
echo ============================================================
if exist build_env (
    rmdir /s /q build_env
)
if exist build (
    rmdir /s /q build
)
if exist dist (
    rmdir /s /q dist
)
if exist GestionChantiers.spec (
    del /f /q GestionChantiers.spec
)
if exist GestionChantiers.exe (
    del /f /q GestionChantiers.exe
)
if exist __pycache__ (
    rmdir /s /q __pycache__
)

echo ============================================================
echo  Installation des composants necessaires (1 a 2 minutes)...
echo ============================================================
python -m venv build_env
call build_env\Scripts\activate
pip install --upgrade pip >nul
pip install -r requirements.txt --no-cache-dir

echo.
echo ============================================================
echo  Fabrication de GestionChantiers.exe en cours (version a jour)...
echo ============================================================
pyinstaller --onefile --noconsole --name GestionChantiers --clean ^
    --add-data "templates;templates" --add-data "static;static" ^
    main.py

echo.
if exist dist\GestionChantiers.exe (
    copy /Y dist\GestionChantiers.exe GestionChantiers.exe >nul
    echo ============================================================
    echo  TERMINE !
    echo.
    echo  Votre logiciel est pret : GestionChantiers.exe
    echo  (juste a cote de ce fichier)
    echo.
    echo  Vous pouvez maintenant :
    echo   - le mettre sur le Bureau ou ou vous voulez
    echo   - double-cliquer dessus pour l'utiliser, comme un vrai logiciel
    echo   - le copier sur une cle USB pour l'installer sur un autre PC
    echo     (le dossier "data" doit toujours rester juste a cote de l'exe)
    echo.
    echo  IMPORTANT : si vous aviez deja un GestionChantiers.exe ouvert,
    echo  fermez-le AVANT de relancer le nouveau, sinon Windows risque
    echo  de garder l'ancienne version verrouillee en memoire.
    echo ============================================================
) else (
    echo  Une erreur est survenue pendant la fabrication.
    echo  Faites une capture d'ecran de ce message et demandez de l'aide.
)
pause
