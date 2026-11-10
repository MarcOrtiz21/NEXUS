# Inspección visual — 9 de octubre de 2026

Alcance: aplicación nativa local, Resumen, Gráficos, perspectiva/gráfico de Oro e
inspector de Semiconductores. Ventanas de 1280×860 y 1800×1053 puntos. No es una
auditoría completa de accesibilidad ni una validación del modelo predictivo.
Los cinco originales de inspección están en `dist/screenshots-real/`, ignorados
por Git; no se ha autorizado su redistribución ni añadido una galería pública.

## Verificado

- [x] La aplicación abre y arranca su motor sin un servidor lanzado a mano.
- [x] Gráficos muestra velas, volumen, MA20/50/200, RSI y MACD; no una demo sintética.
- [x] Oro muestra velas, calendario contextual, RSI/MACD y procedencia/frescura.
- [x] Perspectiva de Oro distingue calidad de datos de confianza predictiva baja.
- [x] El inspector observado es opaco y muestra un cesto de 15 empresas con métricas.
- [x] Capturas PNG obtenidas mediante exportación de la vista visible, sin retoques.
- [x] Compilación release correcta y 281 pruebas Python superadas.

## Pendientes, por prioridad

Estos puntos registran la inspección original. Véase al final el cierre parcial
de 3.17; las comprobaciones pendientes de VoiceOver/otros sistemas no se eliminan.

### P1 — Coherencia y frescura

- [ ] Resolver la incoherencia entre el precio técnico, la serie del inspector y
  la fecha de «última». Durante la inspección SMH mostraba una serie terminada en
  agosto pero «última» en octubre; una consulta posterior de la API ya devolvía
  puntos hasta octubre. Revisar actualización en segundo plano e invalidación
  del estado en memoria. No asumir que el gráfico se actualiza por volver a abrir
  el mismo panel: `ChartDataStore.load` omite entradas ya cargadas sin `force`.
- [ ] En `chart_series.py`, separar la fecha del activo de la del benchmark:
  actualmente `as_of` toma el máximo de ambos. Una fecha reciente de SPY no debe
  rejuvenecer un activo antiguo. Añadir regresión con fechas distintas.
- [ ] Eliminar «ahora por el bloqueo» y «si se levanta el bloqueo» cuando el estado
  de calendario es Libre. Explicar por separado el veto macro, calidad de datos
  y veto de calendario; la acción MANTENER no equivale a bloqueo de calendario.
- [ ] Evitar que HEALTHY parezca garantizar datos frescos: identificarlo como
  estado del motor y mantener visible el estado de cada capa de datos.

### P2 — Lectura y adaptación

- [ ] Alinear el marcador de VIX con los intervalos coloreados: se observa el
  punto en Calma mientras la etiqueta clasifica un valor ligeramente >15 como Normal.
- [ ] Compactar la tabla de plan por activo de Resumen en ventanas anchas: gran
  separación entre nombres y métricas y texto del sesgo FX truncado.
- [ ] Reducir huecos en Oro entre régimen/comparativa y calendario/titulares;
  permitir que el gráfico aparezca antes sin ocultar advertencias.
- [ ] Controlar densidad de velas e indicadores: 6065 velas de cinco minutos en
  un mes hacen poco legible el RSI. Ofrecer zoom/rango adecuado y aviso de densidad,
  sin inventar ni modificar datos para la documentación.
- [ ] Evitar etiquetas de divergencia superpuestas; limitar etiquetas por espacio
  disponible manteniendo el acceso a los eventos y su detalle.
- [ ] Mostrar fechas completas al inicio/fin y evitar recorte del último tick.
- [ ] Ofrecer tabla compacta de empresas para comparar las 15 sin largas tarjetas;
  conservar un detalle ampliable y las advertencias de permiso operativo.
- [ ] Verificar los cambios a 820, 1280, 1440 y 1800 puntos de anchura, además de
  navegación por teclado, VoiceOver, contraste y foco. No darlo por validado con
  las dos ventanas observadas.

## Antes de publicar capturas

- [ ] Corregir primero las incoherencias P1 y repetir la inspección.
- [ ] Revisar derechos de cotizaciones/titulares y excluir todos los bloques
  reservados/locales. La exportación no concede permiso de redistribución.
- [ ] Seleccionar originales con fecha y limitaciones, siguiendo `SCREENSHOTS.md`.
- [ ] Confirmar expresamente la publicación; no se ha hecho commit ni push.

## Seguimiento 3.17 — 11 de octubre de 2026

- [x] Fecha del activo y benchmark separadas en API 1.18; regresiones de activo
  antiguo/benchmark reciente y de benchmark caducado/activo fresco.
- [x] Renovación de gráficos al reabrir y relecturas acotadas durante la carga;
  prueba nativa del paso STALE → FRESH y reutilización de solicitudes recientes.
- [x] Snapshot técnico y gráfica identificados como fuentes con fechas distintas.
  El precio de una vela nueva no recalcula ni rejuvenece el score del snapshot.
  Si la capa no trae fecha, se muestra «sin fecha»; no se inventa una observación.
- [x] Calendario Libre separado del veto operativo y estado de servicio separado
  de frescura. VIX colocado en su banda correcta.
- [x] Ancho real propagado a páginas e inspector: la inspección a 820 detectó
  uso del valor por defecto 1200 en vistas padre; corregido y vuelto a inspeccionar.
- [x] Resumen/Oro/Rotación revisados a 820, 1280, 1440 y 1800 puntos. No constituye
  una prueba exhaustiva de cada pestaña/estado en las cuatro anchuras.
- [x] Liquid Glass con API nativa macOS 26+ y diseño sólido alternativo: ajuste
  encendido/apagado comprobado. Datos e inspector opacos. Botones individuales,
  separados 8 puntos y sin distancia de unión en GlassEffectContainer.
- [x] Tabla de 15 empresas con lectura técnica, advertencia de datos caducados,
  detalle alternativo y acción primaria de apertura. Etiquetas accesibles presentes.
- [x] Aviso de serie densa, fechas extremas y zona horaria del instrumento;
  etiquetas RSI colisionantes omitidas, líneas/eventos conservados y resumen
  de divergencias incluido en el valor accesible.
- [x] 284 pruebas Python y comprobaciones nativas ejecutables con Command Line
  Tools. Compilación release 3.17.0 / API 1.18.
- [x] Fallo intermitente de arranque diagnosticado: espera en os_listdir/open
  durante importación. La interfaz conserva la última fase y no la sobrescribe.
  Dependencias cargadas antes de añadir el proyecto a sys.path; espera acotada
  de 60 s con progreso. No se cambian permisos del SO.
- [ ] Repetir el arranque de la última compilación tras esta corrección y guardar
  evidencia final; los reintentos anteriores sí llegaron a levantar el motor propio.
- [ ] VoiceOver integral, contraste medido de cada estado Glass y ejecución en
  macOS 14/15. El fallback por disponibilidad/accesibilidad está implementado,
  pero no se equipara a ejecutar la aplicación en esos sistemas.

Referencia de diseño: [Adopting Liquid Glass — Apple](https://developer.apple.com/documentation/TechnologyOverviews/adopting-liquid-glass).
No se han publicado imágenes/datos ni hecho commit o push. El modelo de oro y
su protocolo experimental no se han cambiado en esta iteración.

Resultado final del arranque: persiste de forma intermitente la espera importando
Uvicorn, también con el orden corregido y 60 s de presupuesto. El usuario confirma
acceso a Documentos. El cierre del motor propio y dos reintentos con API 1.18 sí
se comprobaron; esto no demuestra que el problema esté resuelto. Para la última
inspección se mantiene el motor de terminal en 127.0.0.1:8765, sin sustituir datos
ni modificar permisos. Este punto sigue abierto.

Enter abre NVIDIA desde la tabla de Semiconductores y conserva ese tema de origen
al volver (antes se elegía el primer cesto coincidente). Verificado en la última
compilación. La exportación AppKit `dist/screenshots-317/rotacion-tabla-export-parcial.png`
contiene la tabla, pero omite la capa GPU de navegación Glass: no es apta para
documentación pública ni evidencia de los botones. Estos se verificaron en las
capturas completas del ordenador, sin reconstrucciones ni retoques.
