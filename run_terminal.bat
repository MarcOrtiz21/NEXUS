@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo  NEXUS - Terminal Macroeconomico (CLI)
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta disponible en el PATH.
    echo Instala Python o abre este script desde un entorno donde python funcione.
    echo.
    pause
    exit /b 1
)

if not exist "main_cli.py" (
    echo [ERROR] No se encontro main_cli.py en:
    echo %cd%
    echo.
    pause
    exit /b 1
)

echo Comprobando dependencias...
python -c "import yfinance, pandas, numpy, requests, rich, feedparser" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Faltan dependencias. Instalando desde requirements.txt...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
)

echo.
echo Iniciando NEXUS en modo terminal...
python "main_cli.py"
if errorlevel 1 (
    echo.
    echo [WARN] Fallo en modo completo. Reintentando sin RSS...
    python "main_cli.py" --no-news
)
if errorlevel 1 (
    echo.
    echo [WARN] Segundo fallback: carga unica compacta sin RSS...
    python "main_cli.py" --once --no-news --compact
)
if errorlevel 1 (
    echo.
    echo [ERROR] NEXUS no pudo arrancar en ninguno de los modos de fallback.
    exit /b 1
)
