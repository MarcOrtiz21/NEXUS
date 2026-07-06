# NEXUS-Macro: Contexto y Reglas del Proyecto

## Rol y Objetivo
El objetivo de este proyecto es construir, optimizar y mantener **NEXUS-Macro** (Networked Economic cross-asset Utility System), una herramienta CLI en Python. Está diseñada para ingerir datos macroeconómicos, procesar reglas de lógica cuantitativa y emitir señales de mercado en la terminal, aislando el sesgo emocional.

## Contexto del Entorno y Arquitectura
El proyecto se desarrolla bajo el directorio local `C:\Users\marco\Documents\NEXUS`. La arquitectura es modular y se divide estrictamente en los siguientes componentes:

- `data_ingestion.py`: Encargado de las conexiones API (yfinance, FRED, Alpha Vantage, etc.) para la extracción de datos brutos.
- `logic_engine.py`: El núcleo matemático. Evalúa umbrales, calcula derivadas de volatilidad y cruza variables para emitir diagnósticos.
- `main_cli.py`: La interfaz gráfica de la terminal. Usa la librería `rich` de Python para mostrar paneles interactivos, tablas y alertas de colores.
- `risk_filters/`: Un directorio para los escudos del sistema, incluyendo análisis de sentimiento de noticias (NLP con FinBERT) y un filtro de calendario económico (bloqueo de señales previas a anuncios de la FED o datos de IPC).

## Variables Core a Monitorizar
1. **VIX (Volatilidad)**: Nivel absoluto y su derivada (tasa de aceleración sobre la media móvil de 5 días).
2. **Correlación Implícita S&P 500**: Alta (pánico/techo) vs Baja (rotación sectorial sana).
3. **Liquidez Global**: Expansión o contracción de la masa monetaria y balances de bancos centrales (ej. FED, Banco Central de China).
4. **Tipos y Bonos**: Rentabilidad del bono estadounidense a 10 años (US10Y) e IPC (Inflación).
5. **Múltiplos de Valoración**: PER estimado vs PER histórico.

## Reglas de Interacción y Código
- Escribir código modular, tipado (`typing` de Python), documentado (Docstrings) y con manejo riguroso de excepciones (las APIs financieras suelen fallar o devolver datos incompletos).
- Separar siempre la lógica de negocio de la lógica de presentación.
- Para implementar un nuevo indicador, primero explicar la fórmula o la lógica macroeconómica detrás de él y luego proporcionar el código en Python.
- Mantener todas las salidas de la terminal, logs y comentarios del código en español.
