# Capturas reales de NEXUS

La documentación visual debe mostrar la aplicación ejecutándose con sus datos
reales, sin fixtures sintéticos, curvas inventadas ni retoques de valores.

**Limitación con Liquid Glass (3.17):** la exportación de la vista con AppKit
puede omitir capas GPU. En la inspección, la tabla se exportó pero la navegación
Glass quedó negra. Ese PNG es una exportación parcial, no una captura fiel de
toda la aplicación, y no debe usarse en el README. Para documentar Glass utiliza
una captura del sistema de la ventana y comprueba visualmente el original; no
reconstruyas ni retoques los botones que falten. La inspección visual con la
captura de pantalla del ordenador sí mostró los botones individuales completos.

## Flujo manual

1. Abre NEXUS y verifica que las gráficas hayan terminado de cargar.
2. Utiliza el mismo tamaño de ventana para cada captura. Muestra Resumen,
   Gráficos, un inspector de Rotación y las vistas pertinentes de Oro.
3. Conserva fechas, estados de frescura, errores y advertencias de fiabilidad.
   Una captura de datos en caché no equivale a una cotización en tiempo real.
4. Selecciona **NEXUS → Guardar vista visible como PNG…** (`⌘⇧S`). La exportación
   copia el contenido visible de la ventana antes de abrir el diálogo: no incluye
   el escritorio ni modifica, descarga o sustituye datos.
5. Guarda los originales primero en `dist/screenshots-real/`, que queda fuera
   de Git. Revisa cada imagen antes de seleccionarla para la documentación.
6. No publiques claves, rutas personales, carteras privadas ni bloques/datos
   locales sujetos a restricciones de terceros. Que un dato sea visible en la
   aplicación no implica permiso para redistribuirlo; revisa también cotizaciones
   y titulares. No publiques WGC, holdings ETF u otras fuentes reservadas sin
   autorización aplicable.
7. Solo tras esa revisión, copia las capturas autorizadas a `docs/images/`, añade
   pies con fecha, sección y limitaciones, y enlázalas en el README. La selección
   de imágenes no autoriza por sí sola un commit o push.

Las estimaciones del oro siguen siendo preliminares: las imágenes no constituyen
evidencia de precisión predictiva ni deben presentarse como resultados validados.
