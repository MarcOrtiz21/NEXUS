@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo  NEXUS Workstation (Desktop App)
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta disponible en el PATH.
    exit /b 1
)

echo Comprobando dependencias...
python -c "import tkinter, yfinance, pandas, numpy, requests, feedparser" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias desde requirements.txt...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar dependencias.
        exit /b 1
    )
)

echo.
echo Iniciando programa local NEXUS...
echo.
python "nexus_desktop.py"
