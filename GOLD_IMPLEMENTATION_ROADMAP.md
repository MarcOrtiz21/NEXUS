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
- [ ] Corregir RBI = India y NBP = Polonia al importar la hoja histórica.
- [ ] Documentar definitivamente WGC, GMC, RG y FMI/3BC.
- [ ] Definir fecha de corte mensual y política de recaptura por evento.
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
- [ ] Incorporar revisiones posteriores como una capa separada de diagnóstico.

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
- [ ] Ingerir reservas y compras oficiales por banco central.
- [ ] Calcular compradores y vendedores líderes móviles a 12 meses.
- [ ] Sustituir tres votos fijos por una contribución agregada y limitada.

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
- [ ] Añadir detección explícita de régimen macroeconómico.
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
- [ ] Importar la hoja `IMPLEMENTAR` como referencia, no como verdad histórica.
- [x] Reconstruir al menos 10 años sin anticipación temporal.

## 6. API de NEXUS

- [x] Exponer `gold.outlook` en el snapshot nativo.
- [x] Exponer horizontes, probabilidad, score y cobertura.
- [x] Exponer grupos y contribuciones.
- [x] Exponer limitaciones y estado de fuentes privadas.
- [x] Exponer recuento histórico y estado de validación por horizonte.
- [x] Exponer calendario mensual específico del oro sin ampliar la ventana de bloqueo operativo.
- [ ] Exponer demanda de bancos centrales.
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
- [ ] Añadir panel de bancos centrales con toneladas y frescura.
- [ ] Añadir histórico de probabilidad, resultado y calibración.
- [ ] `PRIORIDAD MEDIA-BAJA` · Tabla ordenable de factores, fuentes, fecha y frescura.
- [ ] `PRIORIDAD MEDIA-BAJA` · Gráfico de cascada para contribuciones positivas y negativas.
- [ ] `PRIORIDAD MEDIA-BAJA` · Serie temporal de probabilidad frente al resultado posterior.
- [ ] `PRIORIDAD MEDIA-BAJA` · Mapa de calor de inflación general/subyacente y mensual/interanual.
- [ ] `PRIORIDAD MEDIA-BAJA` · Diagrama de calibración previsto frente a observado.
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
- [ ] Acumular 30 resultados vencidos por horizonte antes de publicar métricas.
- [x] Ejecutar ablación por grupo para detectar doble conteo residual.
- [x] Mantener CFTC como contexto hasta que su ablación mejore ambos horizontes fuera de muestra.
- [ ] Exigir mejora estable fuera de muestra antes de elevar la confianza.
- [ ] Documentar limitaciones y periodos en los que el modelo falla.

## 9. Criterios de cierre

- [ ] Cobertura de datos públicos superior al 90% en las capturas mensuales.
- [ ] Cero observaciones posteriores a la fecha de corte.
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
