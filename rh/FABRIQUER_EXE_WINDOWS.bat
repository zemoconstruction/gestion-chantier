@echo off
cd /d "%~dp0"
python -m venv build_env
build_env\Scripts\pip install -q -r requirements.txt pyinstaller
build_env\Scripts\pyinstaller --noconfirm --onefile --noconsole --name RHPro --add-data "templates;templates" main.py
echo Termine : dist\RHPro.exe (le dossier "data" sera cree a cote de l'exe)
pause
