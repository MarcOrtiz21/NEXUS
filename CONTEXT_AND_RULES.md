# NEXUS-Macro: Contexto y Reglas del Proyecto

## Rol y Objetivo
El objetivo de este proyecto es construir, optimizar y mantener **NEXUS-Macro** (Networked Economic cross-asset Utility System), una herramienta en Python para análisis macroeconómico. Diseñada para ingerir datos macro, procesar reglas de lógica cuantitativa y emitir señales de mercado, aislando el sesgo emocional.

## Interfaces
- **CLI** (`main_cli.py`): Dashboard interactivo en terminal con `rich`. Ideal para consultas rápidas.
- **Desktop** (`nexus_desktop.py`): Aplicación local con tkinter, estilo terminal Bloomberg. Refresco automático.
- **Web API** (`web_dashboard.py`): Dashboard con FastAPI (uso interno/opcional).

## Arquitectura Modular

### Núcleo
- `data_ingestion.py`: Conexiones API (yfinance, FRED, Alpha Vantage) para extracción de datos brutos. Caché atómica en disco.
- `logic_engine.py`: Motor lógico. Evalúa umbrales, cruza variables macro, emite diagnósticos y estado de mercado.
- `decision_engine.py`: Capa de decisión multi-activo. Convierte diagnósticos en acción, score, confianza y asignación.
- `rotation_engine.py`: Análisis de rotación sectorial (líderes vs receptores).
- `forex_engine.py`: Motor forex centralizado (EUR/USD vs USD). Señal, semáforo, perspectiva dual, tipo de cambio bidireccional.

### Utilidades
- `utils.py`: Funciones compartidas (build_snapshot, formateo, métricas). Fuente única de verdad para CLI, desktop y web.
- `config.py`: Constantes y umbrales centralizados.
- `user_settings.py`: Preferencias persistidas con thread safety.

### Filtros de riesgo (`risk_filters/`)
- `sentiment.py`: Análisis de sentimiento por keywords ponderadas + FinBERT opcional. Resultado estructurado (no strings).
- `calendar.py` / `fred_calendar.py`: Filtro de calendario económico con manejo DST correcto (zoneinfo).
- `news_feed.py`: Agregación de feeds RSS financieros.

### Histórico y tracking
- `history.py` / `history_view.py` / `history_cli.py`: Exportación y visualización de snapshots históricos.
- `paper_trading.py`: Simulación de cartera con rebalanceo.
- `signal_track_record.py`: Track record de señales emitidas.
- `daily_report.py`: Generación de reportes diarios.
- `backtest.py`: Backtesting de la estrategia con datos históricos.

## Variables Core a Monitorizar
1. **VIX (Volatilidad)**: Nivel absoluto y su derivada (tasa de aceleración sobre la media móvil de 5 días).
2. **Correlación Implícita S&P 500**: Alta (pánico/techo) vs Baja (rotación sectorial sana).
3. **Liquidez Global**: Expansión o contracción de M2 (US y China).
4. **Tipos y Bonos**: Rentabilidad del bono US a 10 años, curva 2Y-10Y, e IPC (Inflación).
5. **Múltiplos de Valoración**: PER forward vs PER trailing, percentil histórico.
6. **Forex**: EUR/USD spot, tipo bidireccional, momentum relativo, sesgo de noticias.

## Reglas de Interacción y Código
- Escribir código modular, tipado (`typing` de Python), documentado (Docstrings) y con manejo riguroso de excepciones.
- Separar siempre la lógica de negocio de la presentación.
- Centralizar funciones compartidas en `utils.py` y umbrales en `config.py`. No duplicar.
- El sentimiento se consume como resultado estructurado (dict), nunca parseando strings de alertas.
- Para implementar un nuevo indicador, explicar la fórmula macro primero y luego el código.
- Mantener todas las salidas de terminal, logs y comentarios del código en español.
