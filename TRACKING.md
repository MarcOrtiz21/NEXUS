# NEXUS-Macro: Seguimiento del Proyecto (TRACKING)

Registro vivo del desarrollo de **NEXUS** (Networked Economic cross-asset Utility System).  
Última actualización: **2026-07-14** — commit `d6eaad8`.

---

## Arquitectura actual (capas)

| Capa | Módulo | Rol |
|------|--------|-----|
| Ingesta | `data_ingestion.py` | yfinance, FRED, Siblis; caché rápida (5 min) + macro lenta (6 h) |
| Motor lógico | `logic_engine.py` | VIX, tipos, correlación, calendario, sentimiento → `MarketStatus` |
| Decisión | `decision_engine.py` | Score macro, asignación, **macro vs operativa** |
| Rotación | `rotation_engine.py` | Leaders vs receivers sectoriales |
| Forex | `forex_engine.py` | EUR/USD, UUP, sesgo noticias |
| Riesgo | `risk_filters/` | Calendario, sentimiento, noticias RSS/NewsAPI |
| Historial | `history.py`, `history_view.py` | Snapshots JSONL/CSV |
| Paper | `paper_trading.py` | Cartera virtual vs buy-and-hold SPY |
| Track record | `signal_track_record.py` | Acierto histórico vs SPY |
| Informe | `daily_report.py` | Export TXT/HTML diario |
| Notificaciones | `macos_notifications.py` | Alertas nativas macOS |
| Ajustes | `user_settings.json` | Refresco, calendario, filtros, FinBERT, notificaciones |
| UI | `main_cli.py`, `nexus_desktop.py`, `web_dashboard.py` | Terminal, desktop, web |
| Utilidades | `utils.py` | `build_snapshot()`, formatters, `trend_label()` compartidos |

### Diagnóstico macro vs señal operativa

NEXUS separa dos lecturas:

- **Diagnóstico macro** — qué dice el mercado (VIX, tipos, liquidez, momentum, global).
- **Señal operativa** — qué hacer ahora; puede estar **pausada** por calendario o sentimiento aunque el macro diga COMPRAR.

Campos en `DecisionResult`: `macro_action`, `operational_action`, `operational_pause_reason`, `macro_allocation`.

---

## Lanzadores macOS (doble clic)

| Archivo | Qué hace |
|---------|----------|
| `setup.command` | Crea `.venv` e instala dependencias |
| `run_terminal.command` | CLI Rich en terminal (modo loop por defecto) |
| `run_program.command` | App desktop tkinter (NEXUS Workstation) |
| `run_nexus.command` | Menú interactivo CLI |
| `run_checks.command` | Tests + smoke CLI + backtest rápido |
| `run_history.command` | Consulta historial de decisiones |
| `run_track_record.command` | Track record NEXUS vs SPY |
| `run_paper.command` | Paper trading + alpha vs SPY |
| `run_dashboard.command` | Dashboard web FastAPI (puerto 8765) |
| `run_daily_report.command` | Exporta informe diario TXT/HTML en `data/reports/` |
| `install_mac_app.command` | Construye e instala `NEXUS Workstation.app` en Applications |

En terminal también existen los `.sh` equivalentes. Windows mantiene `.bat` (paridad parcial).

---

## Configuración y API keys

| Recurso | Ubicación | Uso |
|---------|-----------|-----|
| FRED | `apikeys/FRED.txt` o `FRED_API_KEY` | M2, IPC, 2Y, China M2, **calendario US oficial** |
| NewsAPI | `apikeys/NEWSAPI.txt` o `NEWSAPI_KEY` | Titulares premium (opcional) |
| Ajustes usuario | `data/user_settings.json` | Refresco, bloqueo 3h/6h, filtros, FinBERT, notificaciones |
| Historial | `data/history/decisions.jsonl` | Snapshots exportados |
| Caché | `data/cache/fast_market.json`, `slow_macro.json`, `fred_release_calendar.json` | Precios vs macro lento vs calendario FRED |
| Informes | `data/reports/daily_YYYY-MM-DD.html` | Informe diario imprimible a PDF |

Variables de entorno útiles:

- `NEXUS_CALENDAR_BLOCK_HOURS=3|6` — ventana de bloqueo pre-evento
- `NEXUS_USE_FINBERT=1` — FinBERT opcional (requiere `transformers` + `torch`)

---

## Completado

### Fases iniciales (v1–v2)
- Estructura modular, `data_ingestion`, `logic_engine`, `main_cli` con Rich.
- Escudos de riesgo: calendario y sentimiento por keywords.
- Auditoría v1/v2: bugs críticos corregidos, tests básicos, `requirements.txt`.
- PER, M2, IPC vía FRED; RSS noticias; `config.py` centralizado.

### oleada macOS + analytics (`dd4ebd3`)
- Desktop tkinter, forex, rotación sectorial.
- Calendario RSS Myfxbook, historial JSONL, paper trading, dashboard web.
- Indicadores: curva 2Y-10Y, PER percentil Siblis, China M2 YoY, mercados globales (FEZ, EWJ, FXI, AAXJ).
- Backtest mejorado con `LogicEngine` + series FRED.

### Prioridad alta — confianza y UX (`1de8382`)
- [x] Calendario US-only: solo eventos US verificados bloquean; fix Mauritius/`"us"`.
- [x] Paneles dual macro/operativa en CLI y desktop.
- [x] Track record vs SPY (`signal_track_record.py`, `run_track_record.command`).
- [x] Tests de regresión: calendario, sentimiento, track record, decisión dual (34+ tests).
- [x] Launchers `.command` para doble clic en Finder.

### Prioridad media — profundidad (`1de8382`)
- [x] Caché en capas: precios/VIX 5 min, FRED/PER 6 h.
- [x] Sentimiento ponderado por fuente/recencia; FinBERT opcional para titulares ambiguos.
- [x] Paper trading vs benchmark SPY (alpha).
- [x] Dashboard web ampliado (VIX, curva, rotación, divergencias de señal).
- [x] Ajustes desktop sin terminal (`user_settings.json`).

### Operaciones y CI (`67396b9`, merge `c0b5f2a`)
- [x] Notificaciones macOS al cambiar señal, entrar en BLOCKED/PANIC o VIX > 30.
- [x] GitHub Actions: tests unitarios en push/PR (`.github/workflows/checks.yml`).

### Siguiente oleada (`58dade8`)
- [x] Calendario US vía fechas oficiales FRED (`fred_calendar.py`: CPI, NFP, GDP, PCE, FOMC).
- [x] Europa/China pesan en score macro (`GlobalMarkets` en `decision_engine.py`).
- [x] Pestaña **Track Record** en desktop.
- [x] Informe diario exportable TXT/HTML (`daily_report.py`, pestaña **Informe** en desktop).
- [x] ~~Envío por email del informe~~ — descartado por decisión del usuario.

### Oleada refactor + hardening (2026-07-14)
- [x] **Fase 1 bugs:** FRED calendar con `zoneinfo` + hora ET (DST); paper trading CASH/`entry_prices`; forex sin fabricar momentum parcial; FRED YoY por fecha (`_find_obs_near_date`).
- [x] **Fase 2 DRY:** `utils.py` con `build_snapshot()` canónico; CLI/desktop ~534 líneas menos; `daily_report` usa `utils`.
- [x] **Fase 4 calidad:** sentimiento estructurado (`logic_engine.sentiment_result` → `DecisionEngine`); escritura atómica de caché; `user_settings` thread-safe (fix deadlock lock).
- [x] **Fase 5 UX:** `forex_bidirectional_rates()`; etiquetas claras (`ESPERAR / NO ABRIR`, `MANTENER POSICIONES`); `normalize_action()` en `config.py` para historial/track record.
- [x] **Fase 7 packaging:** `requirements.txt` pinned; fuentes macOS; `build_mac_app.sh` corregido; `CONTEXT_AND_RULES.md` actualizado.
- [x] `_trend_label` unificado en `utils.trend_label` (decision + rotation).
- [x] **Fase 3 config:** umbrales PE/M2/CPI/curva, tablas de asignación y thresholds forex en `config.py`.
- [x] **Fase 6.1 UI:** shell Bloomberg + vistas tipadas Trade Republic en todas las pestañas (`nexus_desktop.py`).
- [x] **App macOS:** `build_mac_app.sh` + `install_mac_app.command` (icono, diálogo de error, install a Applications).

---

## Bugs corregidos (histórico)

| Bug | Fix |
|-----|-----|
| VIX_MA20 N/A con periodo corto | `period="1y"` en yfinance |
| VIX evaluación muerta (if monolítico) | IFs independientes |
| Sentimiento siempre PÁNICO (titulares fake) | RSS real + umbral mínimo 3 hits |
| Correlación con 2 ETFs ruidosa | 5 ETFs, media de 10 pares |
| Correlación negativa mal interpretada | `abs(corr)` |
| HEALTHY con datos críticos incompletos | Validación `CORE_DATA_FIELDS` |
| Calendario manual bloqueaba como oficial | Solo RSS/FRED verificados bloquean |
| Mauritius activaba bloqueo US (`"us"`) | Regex `\b` + whitelist US |
| China M2 YoY mal calculado | YoY % correcto |
| Backtest usaba calendario de hoy en fechas pasadas | `_as_of` en snapshots |
| Import faltante `check_macro_events` en CLI | Import restaurado |
| Paréntesis sin cerrar en desktop overview | SyntaxError corregido |
| Deadlock en `save_user_settings` (lock reentrante) | Lectura disco vía `_read_settings_from_disk()` sin re-lock |
| Track record no reconocía `ESPERAR / NO ABRIR` | `normalize_action()` en config + signal_track_record |

---

## Tests

```bash
./run_checks.command          # tests + smoke + backtest
python -m unittest discover -s tests -v   # solo unitarios
```

Suites: `test_logic_engine`, `test_decision_engine`, `test_rotation_engine`, `test_backtest`, `test_calendar`, `test_sentiment`, `test_signal_track_record`, `test_data_cache`, `test_medium_priority`, `test_macos_notifications`, `test_next_wave`, `test_daily_report`.

**37+ tests** en local (oleada refactor 2026-07-14).

---

## Backlog (pendiente)

### Prioridad media-baja
- [ ] Paridad Windows: `.bat` con historial, dashboard, paper, track record, ajustes.
- [x] App macOS empaquetada (icono, launcher robusto, install a Applications) — `scripts/build_mac_app.sh` + `install_mac_app.command`. Sin firma Apple Developer (opcional).
- [x] Gráfico visual de track record en desktop (ahora es texto).
- [x] Actualizar `CONTEXT_AND_RULES.md` (desktop, utils, ajustes, launchers).
- [x] Centralizar umbrales/allocation/forex en `config.py` (task 3.1–3.3).
- [x] Caché FRED release calendar (5 HTTP por evaluación → 1 refresh cada 6 h).
- [x] Rediseño UI desktop estilo Bloomberg/Trade Republic (task 6.1).

### Prioridad baja
- [ ] README.md de usuario (instalación, launchers, keys, flujo diario).
- [ ] Más mercados en score (Japón/Asia_EM ya pesan menos; afinar umbrales).
- [ ] Fuente BLS directa además de FRED release dates.
- [ ] Export PDF nativo (hoy: HTML → Imprimir → PDF).

### Descartado
- ~~Informe diario por email~~ (no requerido).

---

## Commits de referencia recientes

```
d6eaad8      Refactor DRY, utils.py, action labels, FRED DST, user_settings fix
e5a86d1      Update TRACKING.md with current architecture, launchers, and backlog.
58dade8      FRED calendar, global score weights, track record UI, daily reports
c0b5f2a      Merge macOS launchers, analytics, notifications, CI
67396b9  macOS notifications + GitHub Actions
1de8382  Prioridad alta/media: UX dual, cache, track record, tests
01a4321  macOS .command launchers + fix calendario Mauritius
dd4ebd3  macOS tooling, calendario, historial, paper, dashboard, global markets
```
