@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo  NEXUS - Terminal Macroeconomico
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
echo Elige modo de ejecucion:
echo   1^) Normal ^(mercado + noticias RSS^)
echo   2^) Sin noticias ^(solo mercado/FRED^)
echo   3^) Loop normal ^(refresco cada 5 minutos^)
echo   4^) Ejecutar tests
echo   5^) Normal + exportar historico
echo   6^) Backtest basico
echo   7^) Vista compacta
echo.
set /p choice="Opcion [1-7, Enter=1]: "
if "%choice%"=="" set choice=1

echo.
if "%choice%"=="2" (
    python "main_cli.py" --no-news
) else if "%choice%"=="3" (
    python "main_cli.py" --loop
) else if "%choice%"=="4" (
    python -m unittest discover -v
) else if "%choice%"=="5" (
    python "main_cli.py" --export
) else if "%choice%"=="6" (
    python "backtest.py"
) else if "%choice%"=="7" (
    python "main_cli.py" --compact
) else (
    python "main_cli.py"
)

echo.
if errorlevel 1 (
    echo [ERROR] NEXUS termino con errores.
) else (
    echo NEXUS termino correctamente.
)
echo.
pause
