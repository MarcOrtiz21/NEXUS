# NEXUS-Macro: Seguimiento del Proyecto (TRACKING)

Este documento es un registro vivo del progreso del desarrollo de NEXUS.

## Qué avanzamos (Funcionalidades Completadas)
- **Fase 1:** Inicialización del proyecto, documentación, estructura de carpetas.
- **Fase 2:** `data_ingestion.py` con ingesta de VIX (múltiples temporalidades) y US10Y.
- **Fase 3:** `logic_engine.py` con árbol de decisión y `main_cli.py` con interfaz `rich`.
- **Fase 4:** Escudos de riesgo (`risk_filters/calendar.py` y `risk_filters/sentiment.py`).
- **Auditoría v1:** Revisión completa. 7 bugs críticos detectados y corregidos.
- **Auditoría v2:** Control anti-alucinaciones operativas:
  - `logic_engine.py` ya no confirma `HEALTHY` con datos críticos insuficientes.
  - `risk_filters/calendar.py` distingue calendario estimado de calendario oficial y no bloquea señales con fechas no verificadas.
  - `risk_filters/sentiment.py` expone conteos, tamaño de muestra, términos detectados y método usado.
  - `requirements.txt` creado para instalación reproducible.
  - Tests unitarios básicos añadidos para el motor lógico.
- **Fase 5 (Backlog):** Implementación completa de todas las variables del megaprompt original:
  - PER del S&P 500 (Trailing y Forward) vía yfinance (SPY/IVV/VOO).
  - Liquidez M2 vía FRED API (requiere API key gratuita).
  - Inflación IPC interanual vía FRED API (requiere API key gratuita).
  - Noticias financieras reales por RSS (CNBC + Yahoo Finance, sin API key).
  - `config.py` centralizado para API keys y constantes.
  - Modo loop con `--loop` y `--interval` para refresco periódico.

## Qué fallamos (Errores y Soluciones)
- **Bug: VIX_MA20 siempre N/A.** `period="1mo"` insuficiente. **Fix:** `period="3mo"`.
- **Bug: Evaluación del VIX muerta.** `if` monolítico exigía 4 variables. **Fix:** IFs independientes.
- **Bug: Sentimiento siempre PÁNICO.** Titulares hardcodeados con palabras de pánico. **Fix:** Sentimiento desactivado sin fuente real; ahora usa RSS.
- **Bug: FinBERT nunca se ejecutaba.** `raise ImportError` intencional. **Fix:** Eliminado, honestidad en docstrings.
- **Bug: Correlación ruidosa (2 ETFs).** **Fix:** 5 ETFs sectoriales, 10 pares, correlación media.
- **Bug: Correlación negativa tratada como baja.** **Fix:** `abs(corr)` para evaluar magnitud.
- **Bug: Colores del CLI frágiles.** **Fix:** Enum `MarketStatus` + diccionario de colores.
- **Bug: Sentimiento bloqueaba con 1 solo hit.** 1 palabra negativa de 20 titulares = PÁNICO. **Fix:** Umbral mínimo de 3 señales.
- **Bug: Diagnóstico saludable con datos incompletos.** El motor podía devolver `HEALTHY` si solo había VIX disponible. **Fix:** control de calidad de datos críticos antes de confirmar estado saludable.
- **Bug: Calendario estimado tratado como bloqueo fuerte.** Las fechas manuales podían pausar el sistema como si fueran oficiales. **Fix:** `should_block_signals` solo se activa para calendarios verificados.

## Qué queda por hacer (Backlog)
- [ ] Validar ejecución real de la CLI cuando el terminal vuelva a devolver salida/códigos de estado.
- [ ] Conectar calendario económico oficial o API verificada para activar bloqueos de eventos macro.
- [ ] Investigar por qué `forwardPE` no se expone para SPY/IVV/VOO (podría ser por mercado cerrado en domingo).
- [ ] Añadir más fuentes RSS o integrar NewsAPI para mayor cobertura de sentimiento.
- [x] Implementar tests unitarios para `logic_engine.py`.
- [x] Crear `requirements.txt` para instalar dependencias de un solo golpe.
