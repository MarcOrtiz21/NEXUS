@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo  NEXUS - Checks y Validaciones
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta disponible en el PATH.
    exit /b 1
)

echo [1/3] Ejecutando tests...
python -m unittest discover -v
if errorlevel 1 (
    echo [ERROR] Fallaron tests.
    exit /b 1
)

echo.
echo [2/3] Smoke test CLI (una carga compacta sin RSS)...
python "main_cli.py" --once --compact --no-news --no-clear --max-alerts 3
if errorlevel 1 (
    echo [ERROR] Fallo en smoke test de CLI.
    exit /b 1
)

echo.
echo [3/3] Backtest rapido...
python "backtest.py" --period 2y --rebalance-days 10
if errorlevel 1 (
    echo [ERROR] Fallo en backtest.
    exit /b 1
)

echo.
echo Checks completados correctamente.
