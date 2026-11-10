# Experimento prospectivo de Oro · tendencia–frecuencia v1

Protocolo definido el 8 de octubre de 2026. Es investigación, no una orden
ni una probabilidad validada. No cambia el modelo activo, sus pesos, su
confianza ni sus permisos operativos. No hay cron, automatizaciones ni
capturas programadas.

## Hipótesis y reglas fijadas antes de resultados nuevos

- Instrumento: cierre diario **GLD**, proxy negociable; no oro spot.
- Horizontes: 21 y 63 sesiones diarias observadas de GLD.
- Tendencia: media de los últimos 756 rendimientos logarítmicos diarios;
  volatilidad muestral de los últimos 63. Se exige disponer de al menos
  756 rendimientos, no se sustituye la ventana por dos años disponibles.
- Estimación de tendencia: `Φ(media × √h / volatilidad)`, acotada al
  1–99%. Es un supuesto gaussiano, no una distribución demostrada.
- Frecuencia: proporción de subidas por horizonte en los resultados del
  informe de producción que ya hayan vencido **antes del día del registro**.
  Se congela al registrar; no se reaprende con los resultados futuros.
- Mezcla: **50% tendencia + 50% frecuencia**, sin optimización de pesos.
- Los periodos de investigación ya explorados fijan la frecuencia, pero
  **no** se reutilizan como resultados de este experimento. Sus supuestos
  temporales se conservan en el manifiesto.

## Registro, emisión y disponibilidad

El registro explícito crea `gold-trend-frequency-v1` con fecha real UTC,
reglas, huella de implementación, huella del informe y de producción,
frecuencias y número de casos de origen. Un segundo registro no lo reemplaza.
Si cambian reglas, implementación o producción, el seguimiento se bloquea;
se necesita una nueva versión, conservando esta.

Se guarda el primer corte **manual elegible** de cada mes desde el día 15,
después de las **16:15 de Nueva York**. No se rellenan meses perdidos ni se
retrofechan predicciones. La espera también se mantiene en cierres tempranos,
de manera conservadora. [Horario oficial NYSE](https://www.nyse.com/trade/hours-calendars).

La descarga del histórico diario tiene un límite de 20 segundos. Se exige
caché `OK` de menos de una hora, cierre de la sesión actual, calidad ponderada
de datos activos ≥90% y coincidencia del cierre GLD de producción con el
experimental (tolerancia de un centavo). Una vela del día en curso se excluye
antes de 16:15 ET. Se rechazan cierres duplicados contradictorios.

Leer la pestaña no emite predicciones ni descarga el histórico experimental.
Actualizar manualmente prepara la caché y, si cumple todas las condiciones,
guarda el corte. La vista previa se etiqueta como tal y no cuenta en las métricas.

## Resultados y evaluación

- Predicción, probabilidades de las cuatro referencias, cierre de entrada y
  entradas utilizadas se guardan sin sobrescribir, junto a su hash.
- Se liquida con el cierre de la sesión observada 21/63 posterior a la entrada,
  nunca con una sesión anterior o la propia sesión de entrada.
- Referencias emparejadas: 50% constante, frecuencia congelada, tendencia y
  probabilidad de producción emitida en ese mismo corte.
- Métrica primaria: Brier prospectivo. Métricas auxiliares: precisión
  equilibrada, calibración prevista/observada e intervalos aproximados de
  diferencias de Brier mediante bloques temporales.
- Se ocultan métricas hasta tener ≥30 resultados y ≥30 cortes sin solapamiento
  por horizonte. Ese recuento **no** certifica independencia estadística y,
  con cortes mensuales a 63 sesiones, exige un seguimiento prolongado.
- Solo se señala candidato a **revisión manual** si el límite superior de los
  cuatro intervalos está bajo cero y no empeora precisión equilibrada frente
  a ninguna referencia. No existe promoción automática ni elevación de confianza.
- Un menor Brier no demuestra por sí solo mejor calibración; se debe examinar
  también su curva de fiabilidad. [Documentación de calibración](https://scikit-learn.org/stable/modules/calibration.html).

Los cierres descargados pueden corregirse o contener huecos; no se promete
un archivo oficial point-in-time ni un calendario de negociación completo.
Las entradas archivadas permiten reproducir cada emisión. Los resultados
liquidados se conservan; una revisión del proveedor requiere auditoría explícita,
no reescritura automática. Costes, deslizamiento y rentabilidad operativa no se
evalúan aquí.

## Operación local

Registro inicial explícito: `.venv/bin/python -m gold_experiment --register`.
Preparación manual de precios: `.venv/bin/python -m gold_experiment --prepare-prices`.
El registro solo acepta un informe compatible con las reglas actuales.

Registro, predicciones, entradas y resultados viven en
`data/history/gold_experiments.sqlite3`; precios en
`data/cache/gold_experiment_prices.json`. Ambos están ignorados por Git.
No se introducen nuevas fuentes privadas ni tenencias de ETF en esta hipótesis.
