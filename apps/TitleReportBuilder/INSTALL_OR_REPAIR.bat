@echo off
REM ── Install / repair the Title Report Builder environment ───────────────────
setlocal
cd /d "%~dp0"
set PY=
for %%P in (py python) do (
  %%P -3 --version >nul 2>&1 && set PY=%%P -3 && goto :havepy
  %%P --version  >nul 2>&1 && set PY=%%P     && goto :havepy
)
echo [ERROR] Python 3.11+ not found. Install from https://www.python.org/downloads/.
pause & exit /b 1
:havepy
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv || (echo [ERROR] venv failed & pause & exit /b 1)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Done. Tesseract OCR and LibreOffice (recalc) are optional external tools:
echo   Tesseract:    https://github.com/UB-Mannheim/tesseract/wiki
echo   LibreOffice:  https://www.libreoffice.org/download/
pause
endlocal
