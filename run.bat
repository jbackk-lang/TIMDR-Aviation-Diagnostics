@echo off
title TIMDR-Aviation-Diagnostics -- Dashboard (appka lokalna)
color 0B
cls

cd /d "%~dp0"

echo ============================================================
echo   TIMDR-Aviation-Diagnostics: dashboard (FastAPI)
echo   Katalog roboczy: %cd%
echo ============================================================
echo.

if exist "venv\Scripts\activate.bat" (
    echo [OK] Aktywacja venv...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [OK] Aktywacja .venv...
    call .venv\Scripts\activate.bat
) else (
    echo [INFO] Uzywanie systemowej instalacji Pythona.
)

echo.
echo [1/2] Instalacja pakietow pip...
python -m pip install --upgrade pip --disable-pip-version-check
python -m pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo [BLAD] Instalacja pakietow nie powiodla sie.
    pause
    exit /b 1
)

echo.
echo [2/2] Uruchamianie dashboardu na http://127.0.0.1:8010 ...
echo.
echo (Dane sa statyczne, lokalne (cmapss_fd001_unit1.txt) - appka NIE
echo  wymaga polaczenia z internetem. Zamknij to okno (Ctrl+C), zeby
echo  zatrzymac serwer.)
echo.

start "" http://127.0.0.1:8010
python -m uvicorn webapp.app:app --host 127.0.0.1 --port 8010

pause
