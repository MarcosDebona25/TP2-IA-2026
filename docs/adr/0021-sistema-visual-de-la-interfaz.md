# ADR-0021 · Sistema visual propio para la interfaz: tokens claro/oscuro, tipografía embebida y layout de dashboard clínico

- **Estado:** Aceptado
- **Fecha:** 2026-10-21
- **Relacionado:** presentación final en congreso · ADR-0018 (modo de ejecución visible) · ADR-0019 (reporte estructurado, ids A1, A2…)

## Contexto
La UI Gradio se iba a mostrar en la presentación final de un congreso. Tal como estaba no daba la talla:

- Tipografía serif del sistema (Cambria/Georgia) y cabecera con degradado: aspecto de plantilla, poco legible
  proyectada.
- Emojis como lenguaje visual (pestañas, severidades, estados, títulos), con estilos distintos en cada
  sistema operativo y la apariencia de un prototipo generado.
- Sin selector de modo claro/oscuro (solo el del sistema operativo).
- Layout de una columna larga: alertas como una fila por registro (17 filas para P002) y sin un resumen
  de los indicadores principales.
- Antes de analizar, el panel de alertas decía «Sin alertas»: un falso negativo en pantalla.

## Decisión
1. **Módulo `interface/theme.py`** con todo el sistema visual: tema `gr.themes.Base` (paleta teal sobre
   slate, con variantes `_dark`), tokens CSS `--tp-*` en `:root` (claro) y `.dark` (oscuro), CSS del layout y
   los componentes, y el JS del selector de tema. `app.py` queda con el layout y el wiring.
2. **Tipografía:** Plus Jakarta Sans (texto) y JetBrains Mono (código y logs), **embebidas en base64** desde
   `interface/assets/fonts/` (OFL 1.1). La UI se ve igual sin internet. Cifras tabulares en tablas e indicadores.
3. **Modo claro/oscuro:** botón en la barra superior que alterna la clase `dark` de `<body>` (la misma que usa
   Gradio) y guarda la preferencia en `localStorage`. Sin preferencia guardada manda la del sistema operativo.
4. **Sin emojis decorativos.** Severidad y estados con *pills* de color **y** texto (nunca solo color); iconos
   SVG de trazo fino donde hace falta. Las salidas del grafo (reporte, mensajes del nodo `save`) no se tocan.
5. **Layout de dashboard clínico** en la pestaña Consulta:
   - Barra lateral: ficha del paciente (HTML estructurado), contexto clínico y acción principal.
   - Área principal: franja de indicadores (alertas, HbA1c, glucosa en ayunas, PA con tendencia), y debajo el
     reporte junto al chat de seguimiento. Alertas y tendencias van debajo, a todo el ancho.
   - **Alertas agrupadas** con los mismos ids A1, A2… del reporte (`agents.context.alert_groups`); el detalle
     por registro queda plegado.
   - `alerts_table(None)` («todavía no hay análisis») es distinto de `alerts_table([])` («sin alertas»).
6. Los componentes siguen siendo **funciones puras** en `interface/components.py`, que ahora devuelven HTML.
   `analyze()` devuelve además los indicadores y el encabezado de alertas (7 valores).

## Alternativas consideradas
- **Google Fonts vía `gr.themes.GoogleFont`**: depende de internet en el lugar de la presentación. Se descartó.
- **Inter / IBM Plex Sans**: correctas pero más neutras; se pidió una tipografía más amable. Plus Jakarta Sans
  conserva la legibilidad y tiene un carácter más cálido.
- **Tres columnas (paciente · reporte · chat)**: probado. A 1280–1440 px (resolución típica de proyector)
  dejaba el reporte y las tablas en menos de 560 px, con scroll horizontal. Se descartó.
- **Migrar a otro framework (React/Streamlit)**: fuera de alcance para la fecha; Gradio alcanza con un tema y
  CSS propios.

## Consecuencias
- La UI es consistente en claro y oscuro y se proyecta bien desde 1280 px.
- Cualquier color nuevo se agrega como token `--tp-*` en ambos modos, no como valor suelto.
- Los tests de UI verifican HTML (p. ej. `<dt>Sesiones previas</dt><dd>3`) en vez de Markdown.
- El CSS pisa algunos estilos internos de Gradio (bordes de tablas y el padding de `<button>`). Al actualizar
  Gradio hay que revisarlo a ojo en ambos modos y en celular (390 px).
- Gradio prefija todo el `css` de `launch()` con `.gradio-container… .contain`. Las reglas sobre el
  contenedor o sus ancestros (`.gradio-container`, `.main`, `footer`) van en `theme.HEAD` (`launch(head=…)`);
  si van en `CSS`, no aplican y no da ningún error.
- Se sumó `agents.context.metric_label` para que la tabla de deltas del reporte muestre nombres clínicos
  («HbA1c (%)») en vez de claves internas (`hba1c`).
