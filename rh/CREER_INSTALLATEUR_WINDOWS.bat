@echo off
REM Fabrique dist\RHPro-Setup.exe (installateur avec raccourcis). Pre-requis : Python 3 et Inno Setup 6.
cd /d "%~dp0"
python -m venv build_env || goto :err
build_env\Scripts\pip install -q -r requirements.txt pyinstaller || goto :err
build_env\Scripts\pyinstaller --noconfirm --onefile --noconsole --name RHPro --add-data "templates;templates" --hidden-import waitress main.py || goto :err
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 introuvable : installez-le depuis https://jrsoftware.org/isdl.php puis relancez ce fichier.
  echo En attendant, le programme seul est disponible : dist\RHPro.exe
  pause & exit /b 1
)
%ISCC% installer\RHPro.iss || goto :err
echo.
echo Termine : dist\RHPro-Setup.exe
pause & exit /b 0
:err
echo Une erreur est survenue.
pause & exit /b 1
