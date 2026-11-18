# Auditoría NEXUS · 2026-11-10

Lista de trabajo para agentes. Cada punto es independiente y trae: qué pasa (con la evidencia), cómo hacerlo, y cuándo se considera hecho.

Los números de línea son del árbol de trabajo del 2026-11-10 (incluye cambios sin commit de otras sesiones) y pueden haberse movido: localiza siempre por nombre de función.

**Cómo se verificó cada punto**

- `MEDIDO`: comprobado contra el motor en marcha, las cachés o el historial reales.
- `CÓDIGO`: confirmado leyendo el camino completo en el código.
- `REVISIÓN`: lo señaló una revisión de código y encaja, pero no se ha reproducido. Reprodúcelo con un test antes de cambiar nada.

---

## Reglas para cualquier agente

1. **Paso 0 resuelto para la tanda 1.** El usuario guardó el trabajo anterior en `6459a54`; al iniciar la tanda, este backlog era el único archivo sin seguimiento. Antes de cada nueva tanda, comprobar Git y no mezclar cambios ajenos.
2. **Datos de terceros nunca al repositorio.** Nada de `data/`, descargas, capturas con datos ni exportaciones. Los fixtures de test son sintéticos.
3. **Claves.** No leer, listar ni registrar `APIKEYS/`.
4. **Tests Python:** `.venv/bin/python -m unittest discover -s tests` (288 pasan hoy en ~5 s). Todo cambio lleva test que falle antes y pase después.
5. **App:** `cd native && SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk swift build -c release`, y `bash scripts/test_native_presentation.sh`.
6. **Contrato Python ↔ Swift.** Si cambias una clave del JSON de `/api/native`, cambia `Models.swift` en el mismo trabajo y actualiza el fixture del punto 11.
7. **Sin push a `main`** sin aprobación del usuario. Un commit por punto, mensaje en español.
8. **No ajustar el modelo.** Esta lista no cambia pesos, umbrales de señal ni probabilidades; si un arreglo altera el score, dilo en el resumen.
9. Al terminar un punto: marca `[x]` aquí y anota en una línea qué se hizo y cómo se comprobó.

**Reparto para trabajar en paralelo sin pisarse** (un agente por lote; dentro del lote, en orden):

| Lote | Archivos que posee | Puntos |
| --- | --- | --- |
| A · Ingesta de mercado | `data_ingestion.py`, `rotation_catalog.py`, `config.py` (TTL) | 1, 2, 4, 5, 14, 22, 23, 26, 27, 28 |
| B · Noticias | `risk_filters/news_feed.py`, `risk_filters/sentiment.py` | 13, 24 |
| C · Historial | `history.py`, `history_view.py`, `signal_track_record.py`, `paper_trading.py` | 3, 7, 16, 17 |
| D · API | `native_api.py`, `web_dashboard.py`, `snapshot_service.py`, `logic_engine.py` | 6, 8, 15, 18 (motor), 21, 25 |
| E · Núcleo de la app | `NexusStore.swift`, `APIClient.swift`, `EngineProcess.swift`, `ChartDataStore.swift`, `Models.swift` | 9, 10, 11, 18 (app), 20, 34, 40 |
| F · Pantallas | resto de `native/Sources/NEXUS/*.swift` | 29, 30, 31, 32, 33, 35, 36, 37, 38, 39 |
| G · Repositorio | `.github/`, `requirements.txt`, lanzadores, código heredado | 12, 41, 42, 43 |

Orden recomendado: paso 0 → 12 y 11 (red de seguridad) → 1 a 10 → rendimiento → ingesta → pantallas.

**Decisiones que solo puede tomar el usuario** (los agentes no deben decidirlas): paso 0; retención del historial (16); regla de bloqueo por sentimiento (24); si las peticiones de desempleo bloquean (25); inglés sí o no (36); borrar o archivar el código heredado (41).

---

## 1. Errores que falsean lo que se ve

### [ ] 1. Los precios de las empresas de rotación se quedan congelados · `MEDIDO`

**Qué pasa.** `rotation_companies.json` tiene `captured_at = 2026-11-06T08:16` pese a las actualizaciones del 9 y 10 de noviembre; la cabecera muestra «Empresas 289/299 · 4 d». En `fetch_market_data` (bloque «1b», ~L1422-1468), cuando la caché está «completa» (≥90 %, `_rotation_cache_complete`) solo se descargan los tickers sin precio. Son siempre los mismos 10, fallan, `rotation_cache_updated` queda en `False` y la caché no se vuelve a guardar nunca. Efecto: 292 de 423 entradas de calidad salen `STALE` de forma permanente.

**Cómo hacerlo.**
1. En el bloque 1b, decidir qué descargar así: si `refresh` y la caché no es fresca (`not use_rotation_cache`), descargar **todos** los tickers vivos; si es fresca, nada.
2. Llevar en la propia caché un registro `failed_tickers: {ticker: {"count": n, "last_attempt": iso}}`. Un ticker con 3 fallos seguidos se reintenta como mucho una vez al día y no cuenta para decidir si hay que descargar.
3. `rotation_cache_updated = True` cuando llegue al menos un precio nuevo; al guardar, conservar el último valor bueno de los que fallen en esta pasada.
4. El total de la cabecera debe excluir los tickers marcados como muertos y mostrarlos aparte.

**Hecho cuando.** Test nuevo en `tests/test_data_cache.py`: caché al 96 % con 10 tickers sin precio y `captured_at` viejo → tras `fetch_market_data(refresh=True)` con yfinance simulado se descargan los 289 vivos y cambia `captured_at`. Segundo test: un ticker con 3 fallos no se reintenta dentro de las 24 h.

### [ ] 2. Diez tickers que nunca responden y tres huérfanos en caché · `MEDIDO`

**Qué pasa.** Sin precio en todas las pasadas: `CAJ`, `CHL`, `COMM`, `ESALY`, `JNPR`, `MMC`, `MTRS`, `PCRFY`, `RLNIY`, `TEF` (Canon, China Mobile, CommScope, Eisai, Juniper, Marsh McLennan, Munters, Panasonic, Reliance, Telefónica). Además la caché guarda 302 claves frente a 299 del catálogo (`HAFG`, `LPL`, `SSNLF` sobran).

**Cómo hacerlo.**
1. Para cada uno, comprobar **con yfinance** qué símbolo cotiza hoy (cambio de ticker, exclusión de bolsa, compra). No adivinar: si no se encuentra un símbolo con datos, retirar la empresa del cesto y anotarlo.
2. Corregir en `rotation_catalog.py`. `chart_series.py` ya tiene un mapa de alternativas (p. ej. `SSNLF` → `005930.KS`): reutilizar ese patrón en un único sitio compartido.
3. Al aplicar la caché de rotación, filtrar a `set(ROTATION_COMPANY_TICKERS.values())` para que los huérfanos no vuelvan.

**Hecho cuando.** Cobertura 100 % en vivo (o lista explícita de retirados) y test de que una clave huérfana en caché no aparece en `data["RotationCompanies"]`. Depende del punto 1.

### [ ] 3. El historial de aciertos sale vacío aunque hay 277 muestras · `MEDIDO`

**Qué pasa.** La app muestra «No hay suficientes snapshots separados». `evaluate_track_record(forward_days=5, limit=80)` (`utils.py` ~L130, `native_api.py` ~L298) mira solo las últimas 80 **filas**, que con decenas de capturas al día cubren muy pocos días. Con todo el historial: 277 evaluaciones, 7 independientes. Además el rendimiento a futuro exige que exista una captura 5-8 días después (`_forward_return`), así que depende de haber tenido la app abierta.

**Cómo hacerlo.**
1. Sustituir el límite por filas por una ventana temporal (p. ej. 180 días) y reducir antes a una captura por día (la última de cada sesión).
2. Calcular el precio futuro con cierres diarios de SPY, no con otra captura: usar la serie diaria que ya cachea `chart_series.py` y tomar el cierre de la sesión N posterior. El módulo de oro ya hace algo equivalente (`settle_predictions_from_prices` en `gold_validation.py`): seguir ese patrón.
3. No enviar `samples` completo en `/api/native`; dejarlo solo en `/api/track-record`.
4. Unificar las llamadas (`utils.py`, `native_api.py`, `web_dashboard.py` ~L291, `daily_report.py` ~L30) en una sola configuración.

**Hecho cuando.** Test con historial sintético de 60 días y 30 capturas diarias → tamaño de muestra > 0 e independiente ≈ días/5. Test de que una captura sin otra posterior se liquida con la serie de precios. No cambia ninguna señal: solo la medición.

### [ ] 4. Alertas basadas en series que ya no se publican (China M2 es de 2019) · `MEDIDO`

**Qué pasa.** `China_M2_YoY_Pct` viene de FRED `MYAGM2CNM189N`, cuya última observación es `2019-08-01`. Aun así genera «✅ LIQUIDEZ CHINA EXPANSIVA: M2 YoY = 8.2%» (`logic_engine.py` ~L197-203). No existe ningún tope de antigüedad por observación.

**Cómo hacerlo.**
1. En `data_ingestion.py`, tabla `MAX_OBSERVATION_AGE_DAYS` por serie según su cadencia (diaria 7, semanal 21, mensual 75, trimestral 150). Tras cargar cada serie, si `*_AsOf` supera el tope: valor a `None` y calidad `DISCONTINUED` con el detalle «última observación AAAA-MM-DD».
2. `logic_engine.py` y el score ya ignoran `None`; comprobar que no queda ninguna rama que lo trate como neutral.
3. China: buscar una serie oficial vigente y verificar su última fecha antes de usarla. Si no hay, quitar la alerta y dejar el indicador como «sin fuente vigente».

**Hecho cuando.** Test: observación de 2019 → valor `None`, sin alerta, calidad `DISCONTINUED`. Test por cadencia en el límite.

### [ ] 5. La capa de mercado sale «caducada» 4 de cada 10 minutos · `MEDIDO`

**Qué pasa.** `FAST_MARKET_CACHE_TTL_SECONDS = 360` (`config.py`) y el usuario refresca cada 600 s (`data/user_settings.json`). Entre el minuto 6 y el 10 la capa es `STALE`, y `refine_stance_confidence` (`decision_intelligence.py` ~L275) baja la confianza un escalón. El comentario de `config.py` ya dice que el TTL debe cubrir el intervalo, pero solo cubre el de 5 min por defecto.

**Cómo hacerlo.** Calcular el TTL efectivo como `max(360, refresh_interval_seconds + 90)` leyendo el ajuste del usuario (`user_settings.get_setting`), y usarlo en `_fast_cache_usable` y en `_layer_freshness` de la capa de mercado. No tocar el TTL de macro ni de empresas.

**Hecho cuando.** Test: intervalo 600 s y caché de 500 s → estado `OK`; con 700 s → `STALE`.

### [ ] 6. El motor da estado y plan normales con datos de hace días · `CÓDIGO`

**Qué pasa.** El árbol final de `LogicEngine.evaluate` (`logic_engine.py` ~L283-294) asigna `HEALTHY` si hay «datos mínimos», sin mirar su antigüedad. El 6-nov la app mostró acción, score 35/100 y reparto por activo con datos de 16 días.

**Cómo hacerlo.**
1. Definir «datos demasiado viejos»: capa de mercado con más de una sesión bursátil de retraso (apoyarse en el punto 26 para no penalizar fines de semana).
2. En ese caso: `status = UNKNOWN` con motivo `stale_data`, la decisión conserva el último cálculo pero con `actionable = false` y `stale_since`.
3. Exponerlo en `native_api.py` (`decision.actionable`, `decision.stale_since`) y en `Models.swift`. La parte visual es el punto 30.

**Hecho cuando.** Test en `tests/test_data_cache.py`: caché de 5 días → `UNKNOWN`, `actionable` falso; caché de 10 min → sin cambios respecto a hoy.

### [ ] 7. La cartera simulada registra una «operación» por cada captura · `MEDIDO`

**Qué pasa.** `paper.trade_count = 579`, exactamente las líneas de `decisions.jsonl`. `update_paper_portfolio` (`paper_trading.py` ~L60-110) se llama en cada exportación (`history.py` ~L127) y añade una fila a `paper_trades.jsonl` aunque el reparto no cambie (`action_changed: false`).

**Cómo hacerlo.** Separar valoración de operación: si el reparto normalizado es igual al último (tolerancia 0,5 puntos), actualizar solo el valor de la cartera en `paper_portfolio.json` y no añadir fila. Añadir fila únicamente cuando cambie el reparto. `trade_count` cuenta operaciones reales; añadir `valuation_count` si hace falta.

**Hecho cuando.** Test en `tests/test_paper_trading.py`: tres exportaciones con el mismo reparto → una sola fila; cambio de reparto → segunda fila. El valor de cartera sigue actualizándose.

### [ ] 8. Motor ocupado devuelve error 500 · `CÓDIGO`

**Qué pasa.** `SnapshotService.get` lanza `TimeoutError` si otro hilo calcula y aún no hay instantánea (25 s). `web_dashboard.py` no lo captura (solo hay `HTTPException` en el endpoint de gráficos), así que sale un 500 genérico.

**Cómo hacerlo.** En `api_native` y `api_native_refresh`, capturar `TimeoutError` → `503` con `{"error": "snapshot_busy", "retry_after_seconds": 10}` y cabecera `Retry-After`. En `APIClient.swift`, tratar 503 como «motor ocupado»: reintento con espera, sin mostrar error al usuario hasta agotar reintentos.

**Hecho cuando.** Test nuevo `tests/test_web_dashboard.py` con un constructor bloqueado → 503 y cuerpo esperado.

### [ ] 9. «Reintentar» no descarga datos nuevos · `CÓDIGO`

**Qué pasa.** El botón del aviso de error llama a `store.refresh(persist: false)` (`ContentView.swift` ~L112 y ~L136), que solo relee la caché del motor. Tras fallar una actualización completa, reintentar no la repite.

**Cómo hacerlo.** Guardar en `NexusStore` si el último intento fallido era completo (`lastFailedWasPersist`) y que «Reintentar» use `persist: true` en ese caso o cuando `snapshotIsBehind` sea cierto.

**Hecho cuando.** Comprobación manual descrita en el commit y, si se extrae la decisión a una función pura, test en `native/Tests/PresentationChecks.swift`.

### [ ] 10. La relectura tras un timeout puede pisar datos más nuevos · `CÓDIGO`

**Qué pasa.** `followUpAfterTimeout` (`NexusStore.swift` ~L99-112) se lanza como tarea suelta en cada timeout: no se cancela al cerrar ni al hacer otra actualización, pueden coexistir varias, y asigna `snapshot = next` sin comparar fechas.

**Cómo hacerlo.**
1. Guardar una sola `followUpTask`; cancelarla al empezar `refresh`, al lanzar otra y en `shutdownOwnedEngine`.
2. Aplicar la instantánea solo si su `capturedAtUtc` es posterior a la que hay en pantalla (función pura `shouldApply(new:current:)`).
3. `lastRefresh` debe reflejar la fecha de captura del motor, no la hora de la petición.

**Hecho cuando.** Test de `shouldApply` en `PresentationChecks.swift`: más antigua → no se aplica; igual → no; más nueva → sí.

### [x] 11. Un campo inesperado tumba toda la pantalla; falta test de contrato · `CÓDIGO`

**Qué pasa.** `Models.swift` tiene campos obligatorios dentro de listas y bloques (`StatusChip.label/tone`, `BlockBanner.title/guidance`, `NewsItem.title`, `PricePoint.value`, `GoldReserveRecord.id`). Un solo elemento sin ese campo hace fallar la decodificación de toda la instantánea. No hay ningún test que decodifique un JSON real del motor: `native/Tests` solo cubre reglas de presentación.

**Cómo hacerlo.**
1. Fixture sintético: test Python que construya la instantánea con datos simulados y la escriba en `tests/fixtures/native_snapshot.json`; el mismo test falla si el fixture guardado difiere de las claves actuales (así cualquier cambio de contrato obliga a regenerarlo).
2. En `PresentationChecks.swift`, decodificar ese fixture con `NativeSnapshot` y comprobar 5-6 campos clave.
3. Aislar filas no decodificables en listas descriptivas. El esquema, la fecha, el permiso, el calendario y los avisos de bloqueo mantienen validación estricta; no se infieren permisos por defecto.

**Hecho cuando.** El script de comprobaciones falla si se renombra una clave en Python sin tocar Swift; un fixture con una noticia sin título sigue decodificando el resto.

**Verificado en la tanda 1.** Fixture sintético versionable, generado por el constructor real con entradas simuladas. Se reprodujo el rechazo por `news.items.title` antes del cambio; ahora Swift conserva filas válidas y rechaza permisos ausentes, mal tipados o incompatibles con un bloqueo. Se probó también que renombrar `allows_entry` rompe la comprobación Python. Pasan 289 pruebas Python en una copia sin datos locales y los checks nativos.

### [ ] 12. La compilación de la app en GitHub falla · `MEDIDO`

**Qué pasa.** El último push (`39560b9`) dejó el flujo en rojo: `native-build` usa `runs-on: macos-14` y GitHub responde «The configuration 'macos-14-arm64-us-default' is not supported». Además avisa de Node 20 obsoleto en `actions/checkout@v4` y `actions/setup-python@v5`.

**Cómo hacerlo.** En `.github/workflows/checks.yml`, usar una imagen con SDK compatible con Liquid Glass y añadir la compilación de release y los checks nativos. Detectar el SDK con `xcrun` si no hay un `SDKROOT` válido. Mantener macOS 14 como mínimo de ejecución.

**Hecho cuando.** `gh run list --limit 1` muestra el flujo en verde con los dos trabajos.

**Preparado en la tanda 1.** Workflow migrado a `macos-26` con acciones v7. Compilación de release y pruebas nativas verificadas localmente; falta ejecutar ambos trabajos en GitHub Actions tras publicar los cambios con autorización. El punto sigue abierto por esa comprobación.

---

## 2. Rendimiento

### [ ] 13. Las noticias hacen lenta cada reconstrucción de la pantalla · `MEDIDO`

**Qué pasa.** Perfil de `build_native_snapshot(export=False)`: 7,5 s, de los que 6,7 s son `fetch_news_items`. Dos causas: los 12 RSS se piden uno tras otro (3,2 s) y el enlazado de temas y empresas hace 71.641 llamadas a `_contains_term`, que compila una expresión regular en cada una (3,4 s). Ocurre en **cada** `/api/native` pasado el TTL de 60 s, no solo al actualizar.

**Cómo hacerlo** (`risk_filters/news_feed.py`).
1. Caché en memoria de la lista de titulares con TTL de 10 min; `export=True` la fuerza.
2. Descargar los feeds en paralelo con `ThreadPoolExecutor(max_workers=6)`, respetando el presupuesto de tiempo total.
3. Compilar una sola vez por tema, activo y empresa una expresión con todas las alternativas (`(?<!\w)(?:a|b|c)(?!\w)`, sin distinguir mayúsculas) y aplicar esa.
4. Reservar tiempo para NewsAPI en vez de darle solo lo que sobre.

**Hecho cuando.** Reconstrucción sin descarga < 1 s (medir con el mismo perfil). Test: dos llamadas seguidas hacen una sola ronda de peticiones; test de equivalencia de enlazado entre la versión antigua y la nueva sobre 30 titulares sintéticos.

### [ ] 14. 36 MB de cachés por guardar un año de velas dos veces · `MEDIDO`

**Qué pasa.** `fast_market.json` y `market_data.json` pesan 18 MB cada uno; 12 MB de cada uno es `PriceSparklines` (327 tickers × 252 puntos × 9 campos), idéntico en ambos, y se escriben con `indent=2`. La app solo usa los últimos 42 puntos (`_trim_sparklines`).

**Cómo hacerlo** (`data_ingestion.py`).
1. Averiguar quién necesita aún `market_data.json` (`_load_market_cache`, ~L1158). Si es solo respaldo antiguo, dejar de guardar en él `PriceSparklines`.
2. Guardar sin sangría (`separators=(",", ":")`) y redondear precios a 4 decimales.
3. Bajar `SPARKLINE_POINTS` a lo que realmente consume alguien (comprobar usos de las 252 sesiones antes: medias de 200 se calculan aparte).

**Hecho cuando.** Las dos cachés suman < 6 MB, los 288 tests pasan y la app muestra los mismos minigráficos.

### [ ] 15. Cada respuesta del motor pesa 3,6 MB · `MEDIDO`

**Qué pasa.** Reparto de `/api/native`: minigráficos 2,0 MB (51 %), informe de backtest del oro 1,0 MB (502 muestras, solo cambia al relanzar el backtest), `history_periods` 0,43 MB (repite `latest` con el detalle de calidad en 7d, 30d y 90d), `history` 0,16 MB. `freshness` va duplicado.

**Cómo hacerlo.**
1. Backtest: nuevo `GET /api/native/gold/backtest`; en la instantánea dejar solo el resumen que usa la tarjeta. `GoldResearchViews.swift` lo pide al abrirse.
2. Minigráficos: comprobar qué campos lee `SparklinePoint` en Swift y enviar solo esos; para las ~300 empresas, enviar solo fecha y cierre.
3. `history_periods`: quitar `data_quality` de `latest` (dejar los recuentos) y servir los periodos bajo demanda desde la pestaña Historial.
4. Quitar duplicados (`freshness`, `comparison`, `asset_ranking`).

**Hecho cuando.** Test de presupuesto en `tests/test_native_api.py`: instantánea serializada < 800 KB con datos sintéticos de tamaño real. Coordinar con el punto 11.

### [ ] 16. El historial crece 63 KB por captura y repite capturas idénticas · `MEDIDO`

**Qué pasa.** `decisions.jsonl`: 580 líneas, 36 MB. De cada línea, 65 KB (91 %) es `data_quality`, casi todo el estado de cada empresa de rotación. Hay días con 70-88 capturas, muchas sin ningún cambio.

**Cómo hacerlo** (`history.py`).
1. Guardar de `data_quality` solo los recuentos por estado y las entradas que no estén `OK`, excluyendo `RotationCompanies.*` (basta su recuento).
2. No añadir línea si la huella del contenido (acción, score, reparto, precios redondeados) coincide con la última: actualizar un campo `last_seen` en memoria o ignorar.
3. Script `scripts/compact_history.py` que reescriba el archivo existente con el formato nuevo, **con copia de seguridad previa** en `data/history/`.
4. Retención: **decisión del usuario**. Propuesta: todo lo de los últimos 90 días; antes, primera y última captura de cada día.

**Hecho cuando.** Línea nueva < 8 KB; test de que dos exportaciones idénticas dejan una sola línea; el compactador conserva `captured_at`, acción, score, reparto y precios de todas las filas.

### [ ] 17. El historial completo se lee cinco veces por instantánea · `MEDIDO`

**Qué pasa.** `load_history_jsonl` recorre el archivo entero aunque se pida `limit`; por instantánea hay 5 lecturas completas (2.911 `json.loads`, 0,56 s hoy y creciendo): `native_api.py` ~L257-259 y ~L289, y `utils.py` ~L130.

**Cómo hacerlo.** Cargar una vez por construcción y pasar las filas a `summarize_history`, `load_history_period` y `evaluate_track_record` (añadir parámetro `rows=`). Caché en memoria invalidada por tamaño y fecha de modificación del archivo. Después del punto 16.

**Hecho cuando.** Test que espía la apertura del archivo: una sola lectura por `build_native_snapshot`.

### [ ] 18. La app no se entera cuando el motor ya tiene datos nuevos · `CÓDIGO`

**Qué pasa.** Cuando la tarea programada actualiza a través del motor, la app no lo ve hasta su siguiente ciclo (10 min). Y cada ciclo decodifica 3,6 MB y sustituye toda la instantánea aunque nada haya cambiado, lo que redibuja todas las vistas.

**Cómo hacerlo.**
1. Motor: `GET /api/native/version` → `{captured_at_utc, snapshot_hash, building}` sin reconstruir nada (el hash ya se calcula en `audit.snapshot_hash`).
2. App: sondeo ligero cada 30 s; si cambia el hash, pedir `/api/native`. Si el hash es igual al actual, no reasignar `snapshot`.

**Hecho cuando.** Con la app abierta, `launchctl kickstart gui/$(id -u)/com.nexus.background-refresh` se refleja en pantalla en menos de 1 min. Test del endpoint en `tests/test_web_dashboard.py`.

### [ ] 19. La primera actualización tras días tarda 2,5 minutos · `MEDIDO` (causa sin desglosar)

**Qué pasa.** En frío 2,5 min; en caliente 22 s. Sospechas de la revisión: un subproceso de Python nuevo por cada lote de yfinance (`_run_isolated`), `threads=False`, series FRED pedidas en serie.

**Cómo hacerlo.** Primero medir: registrar la duración de cada fase de `fetch_market_data` (mercado, empresas, PER, FRED, oro) y exponerla en el estado del punto 21. Optimizar solo la fase dominante. No reescribir a ciegas.

**Hecho cuando.** Hay tiempos por fase en el registro y una actualización en frío simulada (borrando cachés en una carpeta temporal) baja de 60 s o queda documentado el motivo.

### [ ] 20. Gráficos: recarga en serie, sin límite en memoria ni limpieza en disco · `CÓDIGO` / `MEDIDO`

**Qué pasa.** `ChartDataStore` vuelve a pedir, una a una y en el hilo principal, todas las series cargadas en cada actualización (`refreshLoaded`, ~L212-228) y nunca descarta entradas (`entries`, ~L41). En disco, `data/cache/chart_series` ocupa 94 MB: 66 tickers, 54 sin tocar desde hace más de 30 días.

**Cómo hacerlo.** App: recargar solo las series visibles, límite de 24 entradas con descarte de la menos usada, recarga en paralelo con `TaskGroup`. Motor: al arrancar, borrar de `chart_series` lo no leído en 30 días.

**Hecho cuando.** Test en `tests/test_chart_series.py` de la limpieza por antigüedad; comprobación de política de descarte en `PresentationChecks.swift`.

---

## 3. Ingesta de datos

### [ ] 21. No hay registro del motor ni estado por fuente · `MEDIDO`

**Qué pasa.** La salida del motor va a una tubería de la que la app solo extrae la fase de arranque (`EngineStartupDiagnostics`); el resto se descarta. En `~/Library/Logs/NEXUS/`, aparte del registro de la tarea programada, lo más reciente es del 1 de octubre. Cuando una fuente falla, solo se ve «calidad de datos baja».

**Cómo hacerlo.**
1. `web_dashboard.py`: `RotatingFileHandler` a `~/Library/Logs/NEXUS/engine.log` (2 MB × 3).
2. Registro en memoria por fuente (mercado, empresas, FRED, PER, cada RSS, NewsAPI, CFTC, GLD, reservas, calendarios): último éxito, último error, antigüedad, número de elementos, duración.
3. `GET /api/status` con ese registro y la última ejecución programada.
4. La parte visual es el punto 32.

**Hecho cuando.** Test que simula el fallo de una fuente y lo ve en `/api/status`; el archivo de registro se crea al arrancar.

### [ ] 22. PER forward: se fía del orden de la respuesta y no caduca · `CÓDIGO`

**Qué pasa.** `data_ingestion.py` ~L1047-1067 toma `valid_rows[-1]` como dato más reciente sin ordenar por fecha. El 6-nov la fecha mostrada era `2026-09-30`: más de cinco semanas, sin ningún aviso.

**Cómo hacerlo.** Ordenar por fecha parseada, rechazar fechas futuras, y aplicar el tope de antigüedad del punto 4 (45 días → `STALE` visible junto al valor). Mostrar siempre la fecha del dato en la app.

**Hecho cuando.** Tests con filas desordenadas y con dato de 60 días.

### [ ] 23. La curva de tipos mezcla dos fuentes con fechas distintas · `REVISIÓN`

**Qué pasa.** `Yield_Curve_Spread` resta el 2 años de FRED (`DGS2`, con su fecha) al 10 años de Yahoo (`^TNX`, último precio). Tras festivos o fines de semana pueden ser de días distintos.

**Cómo hacerlo.** Tomar ambos de FRED (`DGS10` y `DGS2`) para el diferencial y exigir la misma fecha de observación; si difieren en más de 3 días, diferencial `None` con motivo. Mantener `^TNX` solo como nivel intradía.

**Hecho cuando.** Test con fechas desalineadas → diferencial ausente y motivo en calidad.

### [ ] 24. Noticias: calidad de la muestra y bloqueo por sentimiento · `MEDIDO` / decisión

**Qué pasa.** De 117 titulares, 51 caen en «Otros» (incluye titulares ajenos a mercados); Investing.com llega sin fecha de publicación, así que no se pondera por antigüedad; NewsAPI aporta 0. El sentimiento es por palabras clave y pasó de «PANIC» (68,5 frente a 3,9, el 6-nov) a «BULLISH» (27,8 frente a 12,0, el 10-nov). Ese valor puede bloquear señales («sentimiento extremo»).

**Cómo hacerlo.**
1. Titulares sin fecha: peso mínimo y fuera del cálculo de sentimiento.
2. Endurecer `_is_relevant_item` para descartar lo que no enlaza con ningún tema, activo ni evento.
3. NewsAPI: si no hay clave configurada, no intentarlo ni contarlo; si la hay y da 0, registrarlo en el estado (punto 21).
4. Bloqueo: **decisión del usuario**. Propuesta: exigir dos lecturas extremas seguidas separadas ≥30 min y un mínimo de titulares con fecha, y mostrar los titulares que lo provocan.

**Hecho cuando.** Tests de cada regla con titulares sintéticos. La regla de bloqueo (paso 4) cambia cuándo se pausan las señales: documentarlo en el commit y en la hoja de ruta.

### [ ] 25. Calendario: bloqueo semanal y tablas manuales que caducan · `MEDIDO` / decisión

**Qué pasa.** Las peticiones semanales de desempleo están como impacto ALTO y bloquean 3 h **todos los jueves** (`risk_filters/fred_calendar.py`). Hay listas mantenidas a mano que dejan de valer sin avisar: `FOMC_DATES` hasta 2027-12 (`risk_filters/calendar.py`), el identificador del informe semestral de RBI (`gold_demand.py`), y las excepciones de publicación de CFTC (`cftc_positioning.py`, comprobar hasta qué fecha llegan).

**Cómo hacerlo.**
1. Peticiones de desempleo: **decisión del usuario**. Propuesta: impacto MEDIO, sin bloqueo.
2. Función `maintenance_warnings()` que devuelva avisos cuando una tabla manual termina en menos de 60 días o el informe de RBI supera 200 días; exponerla en `/api/status`.

**Hecho cuando.** Test de `maintenance_warnings` con fecha simulada posterior al fin de cada tabla.

### [ ] 26. La antigüedad no tiene en cuenta si el mercado está abierto · `CÓDIGO`

**Qué pasa.** La frescura compara contra la hora actual. Un sábado, un cierre del viernes es el dato correcto y aun así aparece como viejo; y se vuelve a descargar todo aunque no pueda haber cambiado.

**Cómo hacerlo.** Función `last_expected_session_close(now)` para la bolsa de EE. UU. (lunes a viernes, 16:00 de Nueva York; festivos a partir de la propia serie descargada: si el último cierre recibido es el último día hábil, está al día). La capa de mercado es `OK` si contiene esa sesión. Con mercado cerrado y sesión ya descargada, saltar la descarga de precios.

**Hecho cuando.** Tests: sábado con cierre del viernes → `OK`; lunes a las 20:00 con cierre del viernes → `STALE`.

### [ ] 27. Yahoo es la única fuente de precios · `CÓDIGO`

**Qué pasa.** VIX, tipos, índices, ETF y divisas dependen de yfinance. Si falla, se sirve la caché sin alternativa.

**Cómo hacerlo.** Respaldo solo para los datos centrales y solo con fuentes oficiales ya usadas: FRED tiene `VIXCLS`, `DGS10`, `SP500` y `DEXUSEU` (cierres diarios con un día de retraso). Usarlos cuando Yahoo no responda, marcando la fuente y la fecha en la calidad y sin mezclar en un mismo cálculo valores de fechas distintas.

**Hecho cuando.** Test: yfinance simulado caído → VIX y 10 años desde FRED con fuente `FRED:...` y fecha de observación.

### [ ] 28. Escritura de cachés e historial poco robusta · `REVISIÓN`

**Qué pasa.** (a) `json.dumps` sin `allow_nan=False`: un NaN de pandas produciría un JSON que luego no se puede leer y se perdería la caché entera. (b) El archivo temporal tiene nombre fijo (`.tmp`) y el bloqueo de `history.py` es solo entre hilos: el motor y la actualización sin app pueden coincidir. (c) Una escritura de historial interrumpida deja una línea a medias que el lector descarta en silencio.

**Cómo hacerlo.** Limpiar no finitos antes de guardar y usar `allow_nan=False`; temporal con nombre único + `os.replace`; reutilizar el bloqueo `fcntl` de `background_refresh.py` para cachés e historial; contar y registrar líneas descartadas al leer.

**Hecho cuando.** Tests: métrica con NaN no rompe la caché; dos procesos exportando a la vez dejan un JSONL válido.

---

## 4. Pantallas

### [ ] 29. Cuatro avisos distintos para decir «no entrar» · `CÓDIGO` + captura

**Qué pasa.** En Resumen conviven el aviso rojo global (`BlockBannerView`, `ContentView.swift` ~L97), la franja amarilla de error (~L102), la tarjeta principal con «ESPERAR» y el aviso «La operativa no autoriza entradas» (`OverviewView.swift`, `alignmentNotice`).

**Cómo hacerlo.** Un único aviso principal con prioridad fija: error de datos > datos caducados > bloqueo por calendario/sentimiento > conflicto de rotación. Los demás pasan a una línea de detalle desplegable dentro del mismo aviso. Decidir la prioridad en una función pura (`PresentationPolicy.swift`).

**Hecho cuando.** Test de la función de prioridad; capturas a 820, 1280 y 1800 pt con un solo aviso.

### [ ] 30. Los datos caducados se ven igual que los frescos · captura

**Qué pasa.** Con 16 días de antigüedad, la acción, el score y el reparto se muestran con el mismo peso; solo hay un «Caducado» pequeño más abajo.

**Cómo hacerlo.** Cuando `decision.actionable` sea falso (punto 6): atenuar la tarjeta principal y el plan, franja «Datos del 20 oct · actualizando…» encima, ocultar el reparto «si se abre», y mantener visible el progreso de la actualización (punto 34).

**Hecho cuando.** Captura con fixture de datos viejos; comprobación en `PresentationChecks.swift` de que el estado activa el modo.

### [ ] 31. Códigos internos y textos técnicos a la vista · `CÓDIGO`

**Qué pasa.** Se muestran tal cual `BLOCKED`, `HEALTHY`, `PANIC`, `STALE`, `UNKNOWN`, `PARTIAL` (`_status_chip` en `native_api.py` ~L125; `StatusChipView`; pulso de noticias en `GlobalReportViews.swift` ~L500; inspector en `AssetDetailView.swift` ~L447). Las alertas llegan como una frase con emoji, hora en UTC ISO y jerga («fuente: fred_release, confianza: HIGH»). Regiones sin acentos: «Espana», «Japon».

**Cómo hacerlo.**
1. Tabla única en Swift de código → texto (p. ej. `BLOCKED` → «Pausado por evento»), usada en todas las vistas; el código queda solo en la ayuda.
2. Alertas estructuradas desde el motor: `{level, title, detail, when_utc, source}`; la app pone el icono y la hora local.
3. Nombres de región para mostrar separados de las claves (`config.py`).

**Hecho cuando.** Búsqueda en `native/Sources` sin códigos en mayúsculas dentro de `Text(`; test del formato de alertas.

### [ ] 32. La antigüedad de los datos se corta en la cabecera · `CÓDIGO` + captura

**Qué pasa.** `ContentView.swift` ~L257-268: una línea, ancho máximo 220 pt → «Mercado 16 d · Macro 16 d · obs. 20 oct · E…».

**Cómo hacerlo.** En la cabecera, solo la capa más atrasada y un indicador de color. Al pulsar, panel con una fila por capa y por fuente (edad, estado, último error), alimentado por `/api/status` (punto 21).

**Hecho cuando.** A 820 pt no hay texto cortado; el panel lista todas las fuentes.

### [ ] 33. La tabla «Plan por activo» corta la instrucción · captura

**Qué pasa.** La columna «Si se abre» muestra «Comprar dólar (…». Anchos fijos como fracción del ancho (`NexusComponents.swift` ~L471-523).

**Cómo hacerlo.** Columna de instrucción flexible con ajuste de línea; por debajo de ~900 pt, filas apiladas (ya existe `isTabular`). La fila de divisas, a ancho completo.

**Hecho cuando.** Capturas a 820, 1280 y 1800 pt sin puntos suspensivos en instrucciones.

### [ ] 34. Actualizar: sin progreso y con errores del sistema · `CÓDIGO`

**Qué pasa.** Una actualización puede durar hasta 5 min con solo un indicador girando. Los errores muestran `error.localizedDescription` («Se ha agotado el tiempo de espera.») sin decir que el motor sigue trabajando.

**Cómo hacerlo.** Mostrar tiempo transcurrido y fase (del campo `building` y fase de `/api/native/version`, punto 18). Tabla de mensajes propios: tiempo agotado, motor ocupado, motor caído, respuesta ilegible. Distinguir «última actualización correcta» de «último intento».

**Hecho cuando.** Cada tipo de error tiene su texto y su acción; test de la tabla de mensajes.

### [ ] 35. Texto muy pequeño y significado solo por color · `CÓDIGO`

**Qué pasa.** `caption2` (≈10 pt) se usa más de 160 veces para texto explicativo, y hay rótulos de 8 pt (`ContentView.swift` ~L279, `NexusCharts.swift` ~L217). Variaciones en verde y rojo sin signo ni flecha. Sin adaptación al tamaño de texto del sistema.

**Cómo hacerlo.** Mínimo 11 pt para cualquier texto que explique algo; 10 pt solo para rótulos decorativos. Signo y flecha junto al color en todas las variaciones (un único formateador). Medir el contraste de `muted` sobre `card` y subirlo si no llega a 4,5:1. Etiquetas de accesibilidad en botones de solo icono.

**Hecho cuando.** Sin fuentes < 10 pt en el código; capturas antes y después de Resumen e Historial.

### [ ] 36. El inglés está a medias · decisión

**Qué pasa.** Unos 240 textos están escritos directamente en español y no pasan por la traducción; en inglés la app queda mezclada.

**Cómo hacerlo.** **Decisión del usuario:** quitar la opción de idioma o completarla. Si se completa: extraer por pantalla a claves, empezando por Resumen y Ajustes, y añadir una comprobación que falle si aparece un `Text("` con literal en español fuera de la lista permitida.

### [ ] 37. Ajustes: no recuerda la pestaña y limita el intervalo · `CÓDIGO`

**Qué pasa.** `last_view` existe en `user_settings.py` pero Swift no lo lee ni lo guarda: siempre abre en Resumen. El selector de intervalo llega a 10 min aunque el motor admite hasta 60.

**Cómo hacerlo.** Añadir `lastView` a `NativeSettings`, restaurarlo en `bootstrap` y guardarlo al cambiar de pestaña. Añadir 15, 30 y 60 min al selector.

### [ ] 38. Código de pantallas duplicado o sin usar · `CÓDIGO`

**Qué pasa.** `OverviewView.swift` define `dataQualityCard`, `rankingCard`, `allocationCard` y `newsPulseCard` que su `body` no usa (la versión viva está en `GlobalReportViews.swift`). `HistoryViews.swift` tiene 2.694 líneas y mezcla Historial, Divisas, Oro y cartera simulada.

**Cómo hacerlo.** Borrar las tarjetas sin uso. Partir `HistoryViews.swift` en un archivo por pantalla **sin cambiar comportamiento** (solo mover). Hacerlo cuando no haya otro agente tocando esas vistas.

**Hecho cuando.** Compila, las comprobaciones pasan y el diff es solo de movimiento.

### [ ] 39. Mejoras menores de interacción · `REVISIÓN`

Inspector de activo poco descubrible (añadir pista en la tabla); Historial sin ordenar ni buscar; el cursor compartido existe en Gráficos pero no en el inspector; Informe y Resumen repiten contenido. Prioridad baja: hacer solo tras los puntos 29-35.

---

## 5. Mantenimiento

### [ ] 40. Ciclo de vida del motor · `MEDIDO` / `CÓDIGO`

**Qué pasa.** El 10-nov había un motor arrancado el 6-nov, sin proceso padre (PPID 1), con 210 MB, al que la app nueva se conectó sin más. Su línea de comandos (`-m uvicorn …`) es la del arranque antiguo, no la del `EngineProcess.swift` actual: **sin confirmar** qué lo lanzó. La app solo detiene su motor en un cierre ordenado (`willTerminateNotification`); si se cierra a la fuerza queda huérfano. `stopForeignEngine` envía `SIGTERM` al PID que diga `/api/health` sin verificar qué proceso es.

**Cómo hacerlo.**
1. Pasar `NEXUS_PARENT_PID` al motor; un hilo vigilante lo cierra si ese proceso desaparece.
2. `/api/health` devuelve también la ruta del proyecto y la hora de arranque; la app solo reutiliza o detiene un motor cuya ruta coincida con la suya.
3. Averiguar el origen del motor con la línea de comandos antigua (¿app instalada desactualizada respecto al código?).

**Hecho cuando.** Cerrar la app a la fuerza deja el puerto 8765 libre en menos de 10 s; test del vigilante en Python.

### [ ] 41. Código heredado que ya no usa la app · `REVISIÓN` / decisión

**Qué pasa.** Fuera del camino app → `web_dashboard`: `nexus_desktop.py` (1.759 líneas), `macos_vibrancy.py`, `main_cli.py`, `history_cli.py`, `macos_notifications.py`, y una veintena de lanzadores `run_*` en la raíz. Arrastran dependencias (`customtkinter`, `pillow`, `pyobjc-framework-Quartz`, `rich`).

**Cómo hacerlo.** **Decisión del usuario:** archivar en `legacy/` o borrar. Antes, comprobar referencias en `README.md`, `run_checks.*`, CI y tests. Quitar de `requirements.txt` lo que quede sin uso.

### [ ] 42. Herramientas y versiones · `MEDIDO`

**Qué pasa.** No hay analizador estático (ni `ruff` ni `pyflakes` instalados). La versión está repetida a mano: API `1.18` en `web_dashboard.py`, app `3.17.0` en `scripts/build_mac_app.sh`, y el README. La ruta del SDK está fija en los scripts.

**Cómo hacerlo.** Añadir `ruff check` al flujo de CI con reglas básicas (errores y nombres sin definir) sin reformatear el código. Una sola fuente de versión (`VERSION` en la raíz) leída por los tres sitios.

### [ ] 43. Menores · `CÓDIGO`

- `gold_history.py` ~L400: si falta la probabilidad se guarda 50 y «NEUTRAL» como si fuera una predicción válida; debería no guardarse.
- `prior_history_row` (`decision_intelligence.py` ~L477): en lecturas sin persistir, la «comparación con la anterior» usa la última guardada, que puede ser la misma evaluación; marcarlo o compararlo con la instantánea previa en memoria.
- API local sin autenticación para `POST /api/native/settings` y `/watchlist`: riesgo bajo en un Mac de un solo usuario; valorar una cabecera compartida.
- `data/cache/gld_holdings_raw`: 14 archivos y creciendo; antes de limpiar, comprobar qué exige la hoja de ruta del oro sobre conservar originales.

---

## Revisado y descartado

No son problemas; no «arreglar»:

- **M2 «mal calculado».** `M2_Change_Pct` compara con la observación de hace 14 semanas a propósito; la alerta dice «en 14 semanas».
- **`code_stale` no vigila todos los módulos.** Sí lo hace: recorre todos los `.py` de la raíz y de `risk_filters/`.
- **Las rutas síncronas bloquean el servidor.** FastAPI las ejecuta en un grupo de hilos; `/api/health` responde mientras se actualiza.
- **La tubería del motor puede llenarse y bloquearlo.** El lector sigue activo toda la vida del proceso; lo que ocurre es que la salida se descarta (punto 21).
