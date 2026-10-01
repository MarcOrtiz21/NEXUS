# Hoja de ruta · Motor de Oro de NEXUS

Documento vivo para implementar y verificar la nueva pestaña **Oro**. Los
elementos se marcarán al completar código, pruebas y revisión visual.

## Principios no negociables

- [x] Separar la lectura mensual/prospectiva del permiso operativo general.
- [x] Separar las pestañas **Divisas** y **Oro**.
- [x] No tratar un dato ausente como neutral ni como cero.
- [x] Agrupar variables correlacionadas para evitar doble conteo.
- [x] Mostrar dirección, intensidad y cobertura.
- [x] Mostrar fuente y fecha de observación en cada indicador individual.
- [x] Mantener APIs privadas y consensos de pago en `STANDBY`.
- [x] Bloquear cualquier uso de información publicada después de la captura.
- [x] Versionar datos, reglas, pesos y resultados del modelo.



## 1. Contrato y nomenclatura

- [x] Definir horizontes de 21 y 63 sesiones.
- [x] Definir salida `ALCISTA / NEUTRAL / BAJISTA` sin convertirla en orden.
- [x] Definir contribuciones continuas y límites por grupo.
- [x] Corregir RBI = India y NBP = Polonia en la referencia importada, preservando el texto original y la celda.
- [ ] Documentar definitivamente WGC, GMC, RG y FMI/3BC. La hoja ya está contrastada; la expansión de RG y «FMI» y la composición exacta de los tres bancos necesitan confirmación del autor.



### Glosario y procedencia · 2026-09-27

- **WGC**: World Gold Council. Sus tablas, informes y posibles descargas no se integran automáticamente: antes hay que comprobar permiso de uso, almacenamiento y redistribución aplicable a NEXUS. [Condiciones oficiales](https://www.gold.org/terms-and-conditions).
- **GMC**: Gold Market Commentary, serie mensual de comentarios del WGC. Es análisis editorial y no una observación cuantitativa independiente ni un voto del modelo. [Serie oficial](https://www.gold.org/goldhub/research/gold-market-commentary).
- **RG**: `IMPLEMENTAR` contiene «RG (DXY)», «RG (US10)», «RG (XAU/USD)», «RG Real» y «RG Year». La fila real calcula un diferencial manual de rendimiento nominal menos inflación, **no** el rendimiento TIPS del motor. La expansión de RG, el periodo exacto y su regla de signo siguen sin confirmar; los votos de la hoja no puntúan.
- **FMI/3BC**: el autor lo define como resultados de los tres principales bancos de cada país/zona en un periodo parecido. **No es** un total de reservas ni necesariamente una serie del Fondo Monetario Internacional. En `IMPLEMENTAR` el encabezado «FMI/3BC» precede a tres filas de compras de bancos **centrales** (PBoC, RBI, NBP): se conserva como encabezado histórico ambiguo, pero estas filas se clasifican por separado como existencias oficiales nacionales, nunca como resultados de tres bancos comerciales. Pendientes expansión de FMI, territorios, selección de tres bancos, métrica, calendarios y licencias.
- **RBI / NBP**: Reserve Bank of India = India; Narodowy Bank Polski = Polonia. El importador muestra la corrección sin sobrescribir «India / NBP» ni «Polonia / RBI» del libro.
- **Reservas oficiales**: existencias físicas en toneladas por entidad y fecha. Una diferencia entre cortes es cambio de existencias, **no** compras netas intrames ni demanda mundial. El BCE es un área económica, los demás registros son nacionales; no hay total global ni se suman registros como si fueran universales.

- [x] Definir fecha de corte mensual desde el día 15 y recaptura posterior a CPI, PCE, empleo o FOMC.
- [x] Definir unidades canónicas para porcentajes, puntos, contratos CFTC, toneladas y precios.



## 2. Ingesta pública y normalización



### Inflación

- [x] CPI general mensual e interanual.
- [x] CPI subyacente mensual e interanual.
- [x] PCE general mensual e interanual.
- [x] PCE subyacente mensual e interanual.
- [x] Inflación energética mensual e interanual.
- [x] Añadir aceleración de 3 meses anualizada para CPI y PCE.
- [x] Guardar la primera publicación histórica mediante vintages ALFRED.
- [x] Incorporar revisiones posteriores como una capa separada de diagnóstico: primera publicación y última revisión conocida por periodo, con retirada explícita de observaciones y caché independiente.



### Tipos, dólar y liquidez

- [x] Rendimiento real TIPS a 10 años.
- [x] Variación mensual del rendimiento real.
- [x] Inflación implícita a 10 años.
- [x] Dólar mediante fuerza y momentum existentes de UUP.
- [x] Liquidez monetaria mediante M2.
- [ ] Añadir expectativas implícitas de tipos de fondos federales.



### Energía y actividad indirecta

- [x] WTI y variación aproximada de un mes.
- [x] Componente energético del CPI.
- [x] Desempleo y cambio mensual.
- [x] Nóminas y variación mensual.
- [x] Producción industrial mensual.
- [ ] Añadir Brent y diferencial WTI/Brent si demuestra valor incremental.
- [ ] Añadir costes mineros y reciclaje de oro.
- [ ] Añadir demanda de joyería de China e India.
- [ ] Añadir comercio y demanda industrial de metales relevantes.



### Flujos y demanda específica de oro

- [x] Ingerir posicionamiento CFTC/COMEX con fecha real de publicación y caché degradable.
- [ ] Ingerir flujos de ETF respaldados por oro.
  - [x] GLD: tenencias físicas diarias y diferencia de stock, solo como contexto mientras su ablación no apruebe (ver P2 ETF).
  - [ ] IAU y resto de ETF: bloqueados por condiciones de uso o falta de histórico oficial.
- [ ] Ingerir reservas y compras oficiales por banco central.
  - [x] Ingerir el saldo mensual de oro monetario del BCE desde su API pública.
  - [x] Ingerir el saldo semanal publicado por el Tesoro de EE. UU.
  - [ ] Ampliar a China, India, Polonia y otros compradores relevantes con fuentes públicas estables.
    - [x] China SAFE: volumen físico mensual en 10.000 onzas troy finas, convertido a toneladas; comparación con mes anterior y mismo mes del año previo. El valor monetario de la fila Gold se excluye. [Tabla 2026](https://www.safe.gov.cn/en/2021/0203/2045.html) · [tabla 2025](https://www.safe.gov.cn/en/2021/0203/2385.html).
    - [ ] India RBI: algunas ediciones de la tabla «Foreign Exchange Reserves» del [boletín mensual](https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx) separan «Volume (Metric Tonnes)» del valor en USD/INR. **HTML histórico ya parseado y probado** con fecha del boletín y fechas de observación; solo se acepta si la observación tiene como máximo 75 días. El índice vigente el 29-09-2026 enlaza únicamente PDF y `rbidocs.rbi.org.in` no responde desde este entorno. NEXUS puede mostrar la [edición oficial anterior de agosto](https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=24414), con corte 31-07-2026 y **estado ARCHIVO**, sin presentarla como dato vigente. Falta extracción PDF validada o una vía HTML/serie oficial actual, hora de difusión y comparativa de 12 meses; el WSS semanal expresa valor, no volumen.
    - [ ] Polonia NBP: comprobar una serie oficial **versionable de volumen físico** con fecha de publicación. Algunas versiones del [informe de balanza de pagos](https://static.nbp.pl/dane/bilans-platniczy/bopa_en.pdf) mencionan toneladas, pero el PDF se reemplaza y la edición consultada el 27-09-2026 no contiene una tabla de existencias físicas. El XLS mensual de reservas en USD/PLN/EUR es valoración monetaria; la API pública de oro es precio. Hasta localizar un archivo físico estable: `MISSING`, sin estimar toneladas por precio.
  - [x] Mantener la cobertura parcial fuera del score hasta validar representatividad.
- [x] Añadir proxy GLD de presión negociada por precio/volumen, rotulado como proxy y fuera del score.
- [x] Mostrar tenencias reales de GLD junto al proxy, sin sustituirlo: el proxy mide presión negociada y las tenencias, stock físico de un solo fondo. Los datos se almacenan solo en local y no se redistribuyen.
- [ ] Calcular compradores y vendedores líderes móviles a 12 meses.
- [ ] Sustituir tres votos fijos por una contribución agregada y limitada.



### Contrato de procedencia y puertas de fuentes · 2026-09-27

- [x] Cada reserva expone ámbito (`country` o `economic_area`), identificador, tipo `monetary_gold_stock`, toneladas físicas, periodo, URL, calidad y ausencia explícita de `release_at` cuando no se conoce. `change_tonnes` está tipado como diferencia de existencias con intervalo; no como compra. Caché sin dato previo sigue `MISSING`, no `STALE`.
- [x] La cobertura distingue fuentes actuales, archivo oficial anterior, caché caducada y ausentes; el denominador es **el conjunto rastreado**, no el mundo. `world_total_available=false`, `aggregation_allowed=false` y demanda oficial fuera del score incluso si llega un valor manual de compras netas.
- [ ] **P1 RBI**: localizar el fichero oficial por edición, parsear *solo* `Volume (Metric Tonnes)`, asociar periodo y hora/fecha de difusión demostrables, preservar URL/versiones y ensayar unidades, huecos y revisiones. Mantener `MISSING` si falla cualquier puerta.
  - [x] Parser de edición HTML oficial y descubrimiento de enlaces HTML del índice; extrae año/fecha semanal, volumen físico y fecha del boletín, no importes INR/USD. Prueba contra una edición real de mayo de 2026 y fixtures de fuente solo-PDF, datos ausentes y antigüedad.
  - [x] Si la edición vigente es solo PDF, consultar **una** edición anterior identificada por el propio índice oficial; mostrar su saldo únicamente como `ARCHIVED` y solo mientras el corte tenga ≤75 días. El parser se contrastó también con la edición real de agosto de 2026 (fecha abreviada `Aug`, 880,52 t a 31-07-2026).
  - [ ] Recuperar y validar la tabla PDF del boletín vigente o encontrar una serie oficial alternativa con archivo histórico. No aceptar un espejo no oficial como fuente de producción.
  - [ ] Registrar la hora de publicación exacta o aplicar una política temporal conservadora para backtest; comparar revisiones y cerrar QA de 12 meses. Hasta entonces RBI es solo contexto descriptivo cuando exista HTML reciente, nunca señal.
- [ ] **P1 NBP**: localizar archivo mensual histórico de onzas/toneladas físicas, documentar política de revisión y disponibilidad point-in-time; si solo existe valor monetario o PDF sobrescrito, dejar `MISSING` y estudiar IRFCL/IMF con sus condiciones.
- [ ] **P2 ETF**: evaluar datos oficiales de participaciones/toneladas de GLD e IAU (archivo histórico, hora de publicación, licencia de conservación y redistribución). Cada fondo se etiqueta por `fund_id`, nunca «flujos de todos los ETF»; el proxy de volumen actual permanece separado.
  - [x] **Revisión GLD · 2026-09-30.** Fuente oficial: [Historical Archive](https://www.spdrgoldshares.com/usa/gld/) → `api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en` (XLSX, hoja «US GLD Historical Archive»). Diario desde 18-11-2004 (~5.700 filas): cierre, onzas por participación, NAV/participación 10:30 NYT, volumen, onzas totales, **toneladas** y NAV total. Participaciones en circulación = onzas totales / onzas por participación (derivado, se rotula así; ambas cifras proceden del mismo cálculo del fondo). Publicación: el fichero se regenera hacia las 06:00–06:30 NYT del día siguiente (`Last-Modified` 10:31 GMT el 30-09-2026 con dato del 29-09): política point-in-time **dato de T disponible desde la sesión T+1**. El archivo se sobrescribe completo; no hay vintages oficiales, así que la reproducibilidad exige guardar localmente cada descarga con su hash y fecha.
  - [x] **Condiciones GLD.** Los [términos de WGTS](https://www.spdrgoldshares.com/terms-and-conditions/) solo permiten guardar y mostrar la información para **uso personal y no comercial**; copiar, distribuir, publicar o crear obras derivadas exige autorización escrita ([sprdgoldshares@gold.org](mailto:sprdgoldshares@gold.org)), y la hoja *Disclaimer* del XLSX prohíbe expresamente reproducir o redistribuir. Consecuencias para NEXUS (repositorio **público**): los datos y descargas viven solo en `data/cache/` (ignorado por git); nunca se versionan filas reales, ni en fixtures de pruebas (usar valores sintéticos); cualquier uso por terceros o publicación de la serie requiere solicitar permiso antes.
  - [x] **Revisión IAU.** iShares solo muestra el valor vigente de «Tonnes in Trust» y «Ounces in Trust» con fecha `as of`; no hay descarga oficial del histórico diario. Los espejos de terceros no se aceptan como fuente de producción. Opción viable: registrar desde ahora una observación diaria propia (histórico solo hacia delante, sin backfill) y dejar IAU fuera de backtest hasta acumular muestra.
  - [x] **Condiciones BlackRock · 2026-10-01.** Los [términos de BlackRock](https://www.blackrock.com/corporate/compliance/terms-and-conditions) limitan el contenido a uso personal y no comercial y, además, prohíben usar «any robot, spider, intelligent agent, other automatic device, or manual process to search, monitor or copy» el sitio o sus datos sin permiso (solo se exceptúan navegadores web generales). La observación diaria automatizada de IAU queda **BLOQUEADA**: no se implementa ni se sustituye por espejos de terceros.
  - [ ] IAU: solicitar permiso escrito a BlackRock para la observación diaria automatizada. Solo con permiso: ingesta forward-only con `fund_id=IAU`, misma política point-in-time y fuera de backtest hasta reunir muestra suficiente.
  - [x] **Decisión de publicación · 2026-10-01.** Repositorio único y público: el **código** de ingesta GLD es público; los **datos** GLD son solo locales. Nunca se versionan filas reales, descargas, capturas ni exportaciones de la serie; las pruebas usan XLSX sintéticos generados en memoria. Quien use NEXUS descarga los datos por su cuenta desde la fuente oficial y bajo las condiciones de WGTS. Aviso en el [README](README.md#datos-de-terceros), en la cabecera de `gld_holdings.py` y en el panel de la aplicación.
  - [x] Implementar ingesta GLD (`gld_holdings.py`): `fund_id=GLD`, toneladas como unidad canónica, onzas y participaciones derivadas (onzas totales / onzas por participación, rotuladas como derivadas), diferencia de stock a 1/5/21/63 sesiones y percentil a 3 años del cambio de 21 sesiones. Filas `US Holiday` descartadas sin convertirlas en cero.
    - [x] Disponibilidad conservadora: el dato de la sesión T es conocido desde el siguiente día hábil de EE. UU. a las 07:00 NYT. El 01-10-2026 el `Last-Modified` (03:00 GMT) ya incluía la sesión del 30-09, así que la regla no adelanta información.
    - [x] Reproducibilidad local: cada descarga se registra en `data/cache/gld_holdings_raw/manifest.jsonl` con SHA-256, fecha de captura, `Last-Modified`, rango de fechas y **filas históricas revisadas** frente a la descarga anterior; se conservan los últimos 30 XLSX. Caché degradable `OK → STALE → MISSING`.
    - [x] Integración: campos `GLD_Holdings_*` con calidad y fecha, historial con `release_at` (rechaza capturas anteriores a la publicación), payload `gold.demand.etf_holdings`, caché lenta (esquema 15) y capacidad `gold_etf_holdings_gld` en la API 1.15.
    - [x] Panel «Tenencias físicas · GLD» bajo la presión negociada, separado del proxy de volumen: toneladas, sesión y hora de disponibilidad, cambios en toneladas, percentil, participaciones derivadas, estado en el modelo y aviso de datos de terceros. `actual_etf_flows_status = GLD_ONLY`: un fondo no representa los flujos agregados de ETF.
    - [x] Grupo candidato `etf_holdings` (peso 0,06 / 0,08) que solo puntúa con la puerta `feature_gates.etf_holdings = ENABLED`, misma regla que CFTC. El backtest lo evalúa como candidato y comprueba que ninguna tenencia se use antes de su publicación.
    - [x] **Ablación real 2016–2026:** `NEUTRAL` en ambos horizontes. Quitar GLD mejora ligeramente el Brier (Δ −0,0001 a 21 sesiones, −0,0004 a 63), por lo que la puerta queda en `CONTEXT_ONLY` y **no entra en el score**. Brier del modelo completo con los candidatos: 0,2576 / 0,2526 (n = 98 / 96). Confirma el riesgo previsto: los flujos siguen al precio y su información ya la recoge el grupo técnico.
    - [ ] Limitación: el pasado usa la versión actual del archivo, que se sobrescribe; el registro de revisiones solo audita desde la primera descarga local.
- [x] **P2 ALFRED**: visualizar revisión posterior frente a primera publicación por serie, sin reemplazar el vintage histórico de la captura. Panel de nueve series y tres periodos recientes por serie; diferencias en unidades originales, fechas de difusión con precisión de día y ausencias/caché caducada visibles.
- [ ] **P3 WGC / consenso / FMI-3BC**: pasar revisión de licencia, definición por territorio y entidad, periodización, comparabilidad y backtest antes de cualquier ingesta puntuable. Fuentes privadas siguen `STANDBY`.
- [ ] Puerta de activación para una fuente: identidad y unidad física verificadas → periodo y fecha de difusión → historial versionado reproducible → prueba de ausencia/revisión y licencia → valor incremental fuera de muestra. La disponibilidad descriptiva por sí sola **no** autoriza score ni confianza alta.



## 3. Fuentes privadas o con licencia · STANDBY

- [ ] `STANDBY` · Consenso histórico previo a CPI, PCE, NFP y tipos.
- [ ] `STANDBY` · Flujos institucionales o intradía de pago.
- [ ] `STANDBY` · Datos WGC sujetos a condiciones de redistribución.
- [ ] Evaluar proveedor, licencia, coste, estabilidad y derecho de almacenamiento.
- [ ] Mantener entrada manual auditable como alternativa temporal.



## 4. Motor de factores

- [x] Grupo Inflación: combina mensual/interanual y general/subyacente.
- [x] Añadir aceleración anualizada a 3 meses para CPI/PCE general y subyacente sin crear votos independientes.
- [x] Grupo Tipos reales: nivel y cambio sin usar `10Y - CPI` como dato principal.
- [x] Grupo Dólar.
- [x] Grupo Energía.
- [x] Grupo Actividad económica.
- [x] Grupo Liquidez.
- [x] Grupo Riesgo.
- [x] Grupo Técnica del oro.
- [x] Grupo Posicionamiento especulativo limitado, condicionado por ablación fuera de muestra.
- [x] Grupo Demanda oficial preparado, sin inventar datos ausentes.
- [x] Renormalizar pesos solo entre grupos disponibles.
- [x] Limitar la confianza de la versión heurística a `MEDIA`.
- [ ] Incorporar sorpresas estandarizadas cuando exista consenso fiable.
- [ ] Añadir pesos aprendidos por horizonte tras el backtest.
- [x] Añadir clasificación explícita y descriptiva de régimen macroeconómico (TIPS reales y dólar), sin voto ni modificación de pesos.
- [ ] Demostrar valor incremental del régimen por estratos fuera de muestra antes de usarlo en el score. El backtest expone recuentos y Brier por régimen solo a partir de 30 casos comparables; esto todavía no demuestra mejora causal.
- [x] Añadir explicación de cambios frente a la captura anterior.



## 5. Persistencia histórica

- [x] Crear almacén SQLite de observaciones y revisiones.
- [x] Rechazar observaciones cuyo periodo sea posterior a la captura.
- [x] Conservar revisiones sin duplicar valores idénticos.
- [x] Guardar `period`, `observed_at`, valor, unidad, fuente y calidad.
- [x] Incorporar `release_at` verificable en el histórico ALFRED del backtest.
- [ ] Incorporar consenso y dato previo cuando exista fuente verificable.
- [x] Guardar capturas inmutables de 21 y 63 sesiones.
- [x] Registrar versión del modelo y contribuciones usadas.
- [x] Liquidar automáticamente resultados vencidos usando solo sesiones posteriores.
- [x] Importar la hoja `IMPLEMENTAR` como referencia, no como verdad histórica: `gold_reference.py` lee solo esa pestaña en modo lectura, 153 filas de nueve meses de 2026, conserva celdas y rótulos originales, corrige RBI/NBP para presentación y deja todos los votos `score_eligible=false` y `release_at=null`. No escribe en SQLite ni en el workbook.
- [x] Reconstruir al menos 10 años sin anticipación temporal.



## 6. API de NEXUS

- [x] Exponer `gold.outlook` en el snapshot nativo.
- [x] Exponer horizontes, probabilidad, score y cobertura.
- [x] Exponer grupos y contribuciones.
- [x] Exponer limitaciones y estado de fuentes privadas.
- [x] Exponer recuento histórico y estado de validación por horizonte.
- [x] Exponer calendario mensual específico del oro sin ampliar la ventana de bloqueo operativo.
- [x] Exponer demanda oficial parcial y su cobertura sin convertir ausencias en cero.
- [x] Exponer el último informe de validación histórica y la versión evaluada.
- [x] Exponer posicionamiento CFTC, frescura, concentración e histórico normalizado.



## 7. Interfaz y accesibilidad

- [x] Crear navegación independiente para **Divisas** y **Oro**.
- [x] Crear cabecera de perspectiva 1M/3M.
- [x] Mostrar contribuciones por familia con texto y color.
- [x] Mostrar inflación general/subyacente y mensual/interanual.
- [x] Mostrar tipos, dólar, energía, actividad y cobertura.
- [x] Añadir avisos de metodología preliminar y fuentes en standby.
- [x] Mantener rejillas adaptables a ancho de ventana.
- [x] Añadir etiquetas de accesibilidad a las contribuciones.
- [x] Verificar arranque en frío, snapshot, XAU/USD y USD/EUR contra la API real.
- [x] Corregir el salto del inspector al redimensionarlo en una ventana estrecha.
- [x] Ampliar el área de arrastre del inspector.
- [x] Ajustar azul y rojo para contraste AA en texto pequeño sobre tarjetas.
- [x] Evitar alturas máximas rígidas en tarjetas de texto explicativo.
- [x] Mostrar predicciones, observaciones y resultados acumulados en Oro.
- [x] Mostrar una tabla adaptativa del backtest frente a sus referencias.
- [x] Reorganizar el detalle en columnas independientes para eliminar huecos por alturas desiguales.
- [x] Priorizar impulsores y presiones antes del gráfico y plegar factores secundarios.
- [x] Diferenciar visualmente XAU/USD spot de GLD como proxy negociable.
- [x] Separar claramente backtest histórico y seguimiento de predicciones en vivo.
- [x] Alinear la comparación del dólar con UUP, la referencia usada por el modelo.
- [x] Agrupar titulares y calendario en una fila adaptable para aprovechar el ancho disponible.
- [x] Añadir histórico adaptable de probabilidades emitidas en vivo.
- [x] Verificar visualmente la vista panorámica completa (cabecera, gráfico, factores y pie).
- [x] Hacer que el ejecutable SwiftUI sea la identidad real del bundle para permitir inspección por Accesibilidad.
- [x] Añadir un carril de eventos macro a 30 días dentro del gráfico XAU/USD.
- [x] Añadir panel CFTC/COMEX con Managed Money, concentración, divergencia y comparación histórica con oro spot.
- [x] Añadir panel de reservas oficiales con toneladas, cambio, corte y cobertura parcial.
- [x] Añadir panel de presión ETF separando explícitamente proxy de flujos reales.
- [x] Añadir histórico de probabilidad y resultado observado por horizonte.
- [x] Tabla ordenable de factores, fuentes, periodo, publicación conocida y frescura: búsqueda, filtro de incidencias y orden reversible; tabla en ventana amplia y tarjetas en ventana reducida. El impacto repetido se identifica como contribución de la familia, no del indicador.
- [ ] `PRIORIDAD MEDIA-BAJA` · Gráfico de cascada para contribuciones positivas y negativas.
- [x] Serie temporal de probabilidad frente al resultado posterior.
- [ ] `PRIORIDAD MEDIA-BAJA` · Mapa de calor de inflación general/subyacente y mensual/interanual.
- [x] Diagrama de calibración previsto frente a observado, con fallos direccionales y principal impulsor registrado.
- [ ] Probar VoiceOver real, contraste aumentado y tamaños de texto del sistema.
- [x] Verificar navegación por teclado y etiquetas de accesibilidad de controles, métricas y gráficas.
- [x] Completar inspección visual panorámica y del inspector lateral; las rejillas mantienen distribución adaptable y el panel es opaco.



## 8. Validación del modelo

- [x] Añadir pruebas unitarias del agrupamiento y datos ausentes.
- [x] Añadir pruebas del contrato API.
- [x] Crear infraestructura de ventanas walk-forward cronológicas.
- [x] Implementar Brier score, calibración y balanced accuracy.
- [x] Impedir que la liquidación use la sesión de la propia captura.
- [x] Crear backtest walk-forward, nunca partición aleatoria.
- [x] Comparar contra momentum simple y contra dólar + TIPS.
- [x] Comparar también con probabilidad constante del 50% y frecuencia histórica de subidas conocida en cada entrenamiento; evaluar las cuatro referencias sobre los mismos cortes fuera de muestra.
- [x] Purgar resultados de entrenamiento aún no vencidos al comenzar cada ventana de prueba; mostrar ventanas concurrentes y subconjunto sin solapamiento sin equipararlo a muestras independientes.
- [x] Añadir intervalos aproximados del 95% para diferencias de Brier mediante bloques temporales y estabilidad por ventana; contrastar sensibilidad entre primera publicación y revisiones conocidas.
- [ ] Acumular 30 resultados vencidos por horizonte antes de publicar métricas.
  - [x] Mostrar el avance `n/30` y ocultar gráfica de calibración, acierto y fallos en la interfaz hasta que haya 30 resultados vencidos reales por horizonte.
- [x] Ejecutar ablación por grupo para detectar doble conteo residual.
- [x] Mantener CFTC como contexto hasta que su ablación mejore ambos horizontes fuera de muestra.
- [ ] Exigir mejora estable fuera de muestra antes de elevar la confianza.
- [x] Documentar en la interfaz los fallos vencidos de mayor error, su retorno y el impulsor dominante.



## 9. Criterios de cierre

- [ ] Cobertura de datos públicos superior al 90% en las capturas mensuales.
- [x] Cero observaciones almacenadas posteriores a la fecha de corte, con auditoría persistente de rechazos e incumplimientos.
- [x] Un fallo de fuente no impide abrir la aplicación; se conserva caché y se expone su calidad.
- [x] La interfaz explica el porqué de cada dirección sin depender del color.
- [ ] El modelo supera las referencias simples fuera de muestra.
- [x] Inspección funcional y visual aprobada antes de publicar la versión 3.9.0.



## Verificación de la versión 3.9.0 · 2026-09-20

- [x] Arranque directo desde Finder y conexión automática con el motor local.
- [x] Actualización manual completa; mercado y macro pasan a estado actualizado.
- [x] Cambio independiente de intervalo y ventana histórica en XAU/USD.
- [x] Apertura, ancho estable y cierre del inspector de activo sin transparencias.
- [x] Desplegado de factores secundarios y lectura accesible de factores sin score.
- [x] Panel CFTC/COMEX, histórico normalizado, concentración y procedencia visibles.
- [x] API 1.11, aplicación 3.9.0, compilación de producción y suite automática verificadas.



## Avance de la versión 3.10.0 · 2026-09-20

- [x] Reservas oficiales del BCE y del Tesoro de EE. UU. con toneladas, comparativa y caché degradable.
- [x] Proxy de presión negociada de GLD con volumen real, separado de flujos/tenencias del ETF.
- [x] Cobertura parcial, datos caducados y ausencias expresados sin convertirlos en cero ni señal neutral.
- [x] API 1.12, aplicación 3.10.0, compilación de producción y suite Python verificadas.
- [x] Contrato real verificado: BCE 508,4 t, Tesoro de EE. UU. 8.133,5 t y proxy GLD disponible.
- [x] Inspección visual final de la tarjeta en ventana ancha y en la anchura mínima admitida (~900 px): distribución estable, navegación adaptable y contenido legible sin recortes ni transparencias.



## Avance de la versión 3.11.0 · 2026-09-22

- [x] Política auditable de corte mensual desde el día 15 y recaptura por evento macro relevante.
- [x] Persistencia del tipo de captura, evento detonante, fecha de corte y observaciones futuras rechazadas.
- [x] Auditoría acumulada de fugas temporales y estado visible en la pestaña Oro.
- [x] Resultado observado junto a cada probabilidad vencida de 21 y 63 sesiones.
- [x] Calibración prevista frente a observada y diagnóstico de fallos direccionales.
- [x] API 1.13, aplicación 3.11.0, compilación de producción, suite automática (199 pruebas) e inspección visual verificadas en ventana amplia y reducida; arranque en frío del motor confirmado.
- [x] El corte comprueba también la hora de publicación CFTC con zona horaria: rechaza publicaciones posteriores y bloquea la persistencia de la predicción completa si hay datos rechazados. El estado visual distingue «SIN FUGAS» de «FILTRO APLICADO».
- [ ] Validar calibración y diagnóstico de fallos con resultados en vivo vencidos: el recuento cambia con cada captura; consultar la API en vez de congelarlo aquí. No se puede declarar calibrado el modelo hasta reunir al menos 30 resultados por horizonte.



## Revisión de `IMPLEMENTAR` y secuencia actual · 2026-09-27

1. [x] Separar `FMI/3BC` (definición pendiente de bancos de cada territorio) de reservas oficiales de PBoC, RBI y NBP. Los `+1/-1` de mayo-septiembre y otros meses son juicios manuales no verificables, no etiquetas de entrenamiento ni compras medidas.
2. [x] Fijar procedencia por celda, país/área y calidad; bloquear extrapolación mundial y la entrada accidental al score. Los datos actuales de BCE, Tesoro y SAFE son contexto parcial; RBI/NBP siguen pendientes de volumen físico extraíble y reproducible.
3. [ ] Resolver RBI/NBP con las puertas anteriores y después ETF reales/tenencias. El diagnóstico de revisión ALFRED ya está implementado por separado. No introducir valores de reservas por conversión de moneda/valor ni atribuir flujos a partir del volumen negociado.
4. [ ] Con el autor, cerrar nomenclatura RG y FMI/3BC y definir un dataset de bancos comerciales individualizado por país/zona; no mezclarlo con PBoC/RBI/NBP ni con WGC.
5. [ ] Solo después de cobertura, derechos, timestamp y suficiente histórico: contrastar pesos/regímenes con ablación walk-forward contra momentum y dólar+TIPS. La validación histórica actual sigue **preliminar** y no demuestra mejora consistente; mantener sin permiso operativo nuevo.



### Ejecución RBI · 2026-09-29

- [x] El HTML oficial de la [edición del 22-05-2026](https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=24213) devuelve 880,52 t con corte 24-04-2026. Solo se usa como verificación del parser, no como saldo actual.
- [x] El índice oficial de septiembre responde, pero para la tabla 33 ofrece PDF. Su servidor no permite recuperar el documento desde este entorno. NEXUS consulta el archivo oficial de agosto y expone 880,52 t a 31-07-2026 como `ARCHIVED`, nunca como dato vigente; vencido el límite de 75 días pasa a `MISSING`. Un valor monetario o una copia externa no reemplazan toneladas oficiales.
- [x] API: `release_date` separada de `release_at` (hora desconocida); SwiftUI muestra la fecha y advierte que la hora no está verificada. La caché RBI antigua no se promociona a dato vigente.
- [x] Otro ajuste de presentación: la tarjeta de Oro desglosa fuentes actuales, de archivo, de caché y ausentes. La variación de toneladas usa color neutral y se etiqueta como cambio de saldo, no como compra o señal.
- [ ] Próxima puerta: conseguir la edición PDF o API oficial de RBI y fixture reproducible, implementar extractor por tabla con pruebas de unidad/fecha/revisión y verificar en pantalla antes de marcar esta fuente como completa.



## Avance de la versión 3.12.0 · 2026-09-30

- [x] Cuatro referencias comparables fuera de muestra: 50% constante, frecuencia de subidas del entrenamiento, momentum y dólar + tipos reales. La frecuencia no conoce resultados pendientes al corte.
- [x] Ventanas cronológicas purgadas por vencimiento; intervalos de Brier aproximados mediante 1.000 remuestreos de bloques, estabilidad por ventana y diagnóstico de solapamiento. No se estima independencia a partir del subconjunto no solapado.
- [x] ALFRED `output_type=1`, paginación y caché independiente; preservación de primeras publicaciones, selección de la revisión conocida al corte y tratamiento de retiradas. Se compara el resultado histórico de ambas políticas, sin modificar predicciones emitidas.
- [x] Diagnóstico real de nueve series ALFRED, tres periodos por serie y diferencias en la unidad original. No introduce nuevos votos en la perspectiva.
- [x] Oro prioriza perspectiva, impulsores, cambios, calendario y titulares. Datos/fuentes, revisiones, demanda/posicionamiento y validación disponen de controles para desplegar el detalle.
- [x] Barra superior sin desbordamiento en media pantalla: menú de secciones compacto y estado limitado con texto completo en la ayuda. Ajustes y Actualizar permanecen visibles. Los controles y cifras desplegables del backtest conservan sus hijos accesibles.
- [x] Tabla de 36 indicadores en la captura inspeccionada, con búsqueda, ordenación reversible, filtro de incidencias y diseño de tarjetas en ventana reducida; fecha de publicación desconocida no se infiere de la descarga.
- [x] API 1.14 y aplicación 3.12.0 empaquetadas. Suite automática: 220 pruebas; compilación de producción correcta. Inspección funcional de búsqueda, ordenación, incidencias y despliegue de revisiones/comparaciones; inspección visual en ventana amplia y media pantalla.
- [x] Nuevo informe 2016–2026: 98 cortes de prueba a 21 sesiones y 96 a 63; Brier 0,2574 / 0,2523, precisión equilibrada 47,6% / 44,5%. **No demuestra mejora estable frente a las cuatro referencias**: `KEEP_PRELIMINARY`. No se elevan confianza ni permisos operativos.
- [ ] Completar prueba manual con VoiceOver real, contraste aumentado y tamaños de texto del sistema. La navegación por teclado y las etiquetas del árbol de accesibilidad sí se han comprobado; esto no equivale a certificar todo el recorrido con lector de pantalla.
- [ ] Pendientes de fuentes: RBI vigente/archivo físico de NBP, ETF reales y cierre de nomenclatura RG/FMI-3BC. Fuentes privadas y consensos siguen en `STANDBY`.



## Avance de la versión 3.13.0 · 2026-10-01

- [x] Tenencias físicas de GLD integradas de extremo a extremo: ingesta, caché y registro de descargas, campos con calidad, historial point-in-time, backtest, API 1.15 y panel nativo. Detalle en «P2 ETF».
- [x] Decisión documentada: código público, datos GLD solo en local; README, módulo y aplicación lo indican.
- [x] Ablación real: GLD `NEUTRAL` y fuera del score. El modelo sigue en `KEEP_PRELIMINARY`.
- [x] IAU revisado y bloqueado por los términos de BlackRock sobre acceso automatizado; pendiente de permiso.
- [x] Suite automática: 231 pruebas; compilación de producción Swift correcta (SDK 26.5).
- [ ] Inspección visual del panel GLD en ventana amplia y media pantalla, y prueba con VoiceOver.
- [x] Motor desfasado: la app reutilizaba cualquier motor que respondiera en :8765. Un proceso huérfano de la versión anterior servía código antiguo contra cachés nuevas (HTTP 500, app sin datos). `/api/health` expone `pid` y `code_stale` (algún `.py` modificado tras el arranque) y la app lo sustituye.
- [x] Arranque desde la app en macOS 27: tras reinstalar la app o actualizar Python con Homebrew (3.12.14 → 3.12.15 el 01-10-2026), el Python lanzado por la app se quedaba bloqueado en `Py_Initialize` leyendo el repositorio en Documentos. Con el permiso «Archivos y carpetas» concedido, la app arranca el motor en 2 s; el mensaje de error lo indica si vuelve a ocurrir tras una reinstalación.



## Calibración y pesos aprendidos · 2026-10-01

Diagnóstico previo con el informe real: la señal heurística no aporta sobre la frecuencia histórica. Correlación con el resultado −0,03 a 21 sesiones y −0,17 a 63; entre 2023 y 2025 el oro subió en 24 de 24 cortes a 63 sesiones con probabilidades medias del 46–49%. La ablación señala a tipos reales (`REVISAR` a 63 sesiones) y dólar como los grupos que más restan; técnica y liquidez aportan a 63. No se modifican pesos heurísticos con esta misma muestra.

- [x] `gold_calibration.py`: tres candidatos ajustados en cada ventana walk-forward solo con resultados vencidos y evaluados con las mismas cuatro referencias e intervalos por bloques.
  - Calibración: p' = frecuencia del entrenamiento + k·(p − 50), con k ∈ [0, 1].
  - Pesos aprendidos: regresión logística con penalización L2 (λ = 4, fijada a priori) sobre las señales de los diez grupos.
  - Régimen 2022: lo mismo más un coeficiente propio de tipos reales desde 2022-03-01. **Hipótesis elegida tras ver 2023–2025**; solo se aprende cuando el entrenamiento ya incluye ese periodo.
- [x] Resultado fuera de muestra (informe 2016–2026, esquema 3):

  | Horizonte | NEXUS | Frecuencia histórica | Calibrada | Aprendida | Aprendida + régimen |
  | --- | --- | --- | --- | --- | --- |
  | 21 sesiones | 0,2576 | 0,2481 | 0,2496 | 0,2573 | 0,2577 |
  | 63 sesiones | 0,2526 | 0,2298 | 0,2298 | 0,2205 | 0,2202 |

  - A 21 sesiones nada supera a la frecuencia histórica; la calibración ajusta k = 0.
  - A 63 sesiones los pesos aprendidos superan en promedio las cuatro referencias (precisión equilibrada 52,3%), pero el IC95% frente a la frecuencia histórica cruza cero (límite superior +0,005): **no concluyente**, sigue fuera del score.
  - El término de régimen no aporta (Δ −0,0003); su coeficiente sale más negativo después de 2022, no invertido. La hipótesis de ruptura no se confirma como mejora predictiva.
  - Coeficientes aprendidos con toda la muestra a 63 sesiones: técnica +0,42, actividad +0,44; inflación −0,68, tipos reales −0,57, energía −0,32 (signo contrario al de la heurística en inflación y energía). Son descriptivos y no autorizan pesos nuevos.
- [x] En vivo: cada horizonte muestra la probabilidad heurística y, si la calibración mejora al modelo y al 50% fuera de muestra, la probabilidad calibrada con su explicación. La etiqueta direccional sigue siendo la heurística. Hoy k = 0: 56% y 66%, la frecuencia base.
- [x] Interfaz: «Calibrada con el histórico» en cada horizonte; candidatos con Brier, Δ frente a NEXUS, precisión equilibrada e IC frente a la frecuencia histórica en la tarjeta del backtest.
- [ ] Repetir la evaluación al acumular cortes nuevos. Promover pesos aprendidos a 63 sesiones solo si el IC frente a las cuatro referencias queda por debajo de cero en dos regeneraciones consecutivas.
- [ ] Incorporar resultados vencidos en vivo a la calibración cuando haya ≥30 por horizonte.

## Calendario macro con fuentes oficiales · 2026-10-01

Diagnóstico: Myfxbook devuelve HTTP 403 de forma permanente (calendario y dos fuentes de noticias). El identificador FRED 677 «FOMC Press Release» no existe, así que las reuniones del FOMC nunca llegaban como evento oficial; el respaldo manual tenía tres fechas de 2026 erróneas (06-05, 04-11 y 16-12 frente a 29-04, 28-10 y 09-12).

- [x] `risk_filters/fomc_calendar.py`: reuniones programadas desde la página oficial de la Fed. La decisión es el último día de reunión a las 14:00 ET; se descartan reuniones no programadas y votaciones por escrito. Caché local de 7 días, uso de la caché caducada si la página falla y espera de 15 minutos entre reintentos sin caché.
- [x] FRED: se elimina 677 (el release 101 tampoco sirve porque incluye series diarias). Se añaden PPI, ventas minoristas y peticiones de subsidio (08:30 ET, bloquean) y JOLTS (10:00 ET, contexto, no bloquea). La caché se recarga si le falta algún release configurado.
- [x] Myfxbook retirado del calendario y de las noticias. Fuente del calendario: `fred_release` o `fed_fomc_calendar`, ambas con confianza alta y hora oficial; el respaldo manual sigue sin bloquear.
- [x] Respaldo manual FOMC corregido con las fechas oficiales de 2026 y 2027.
- [x] Calendario mensual del oro: incluye FOMC oficial, PPI y ventas minoristas. Verificación en vivo: NFP 02-10, CPI 14-10, PPI y ventas minoristas 15-10, PCE 27-10 y FOMC 28-10 a las 18:00 UTC.
- [x] Suite: 247 pruebas con HTML sintético; compilación Swift correcta.
- [ ] Decisiones del BCE: ya no llegan desde Myfxbook. Candidata: página oficial del calendario de reuniones del BCE, con el mismo patrón de caché.