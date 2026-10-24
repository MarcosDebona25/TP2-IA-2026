# Documentación

| Carpeta / archivo | Qué hay |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Guía completa del proyecto: arquitectura, convenciones y estado de cada módulo. |
| [plan_correcciones.md](plan_correcciones.md) | Fuente de verdad de las correcciones pendientes (issues EAS-* en Linear). |
| [adr/](adr/README.md) | Decisiones de arquitectura (ADR-0001 a ADR-0022). |
| [consigna/](consigna/) | Enunciado del TP y definición conceptual del sistema. |
| [tecnica/](tecnica/) | Documentación técnica: [interfaz](tecnica/interfaz.md), [logs](tecnica/logs.md), [tests](tecnica/tests.md) y diagramas (`architecture.puml`/`.png`, `langgraph.png`). |
| [planificacion/](planificacion/) | Estado del proyecto, plan MVP, plan del integrante D y roadmap de mejoras. |
| [capturas/](capturas/) | Capturas de la interfaz actual y el script que las genera. |
| [branding/](branding/) | Logo e isotipo en sus variantes (más `branding.zip`). |
| [publicaciones/conaiisi/](publicaciones/conaiisi/) | Paper para CONAIISI 2026 (versión general e investigadores) y la entrega. |
| [publicaciones/jit/articulo/](publicaciones/jit/articulo/) | Artículo JIT 2026: entrega original, `correccion/` (versión corregida, figuras y [verificación de cambios](publicaciones/jit/articulo/correccion/VERIFICACION_CAMBIOS_JIT.md)) y `devolucion/` (rúbricas de los evaluadores). |
| [publicaciones/jit/presentacion/](publicaciones/jit/presentacion/) | Presentación oral JIT 2026: plantilla y rúbrica oficiales, prompt maestro, capturas, diagramas y recursos. |

## Capturas de la interfaz

Tomadas con el LLM activo (`deepseek-flash`), tema claro, página completa a escala 2.

| Archivo | Contenido |
|---|---|
| `00-inicio.png` | Pantalla inicial, sin paciente elegido. |
| `01-consulta-P001.png` … `01-consulta-P005.png` | Consulta de cada paciente del fixture (reporte, alertas y tendencias). |
| `02-chat-seguimiento.png` | Pregunta de seguimiento sobre el reporte de P003. |
| `03-observabilidad.png` | Traza estructurada del grafo. |
| `04-evaluacion.png` | Historial de la evaluación cualitativa. |
| `portada.png` | Recorte de `01-consulta-P003.png` (1600×1000) que usa el README; se rehace a mano. |

Para regenerarlas, con la app levantada (`uv run python main.py`):

```bash
uv run --no-project --with playwright python docs/capturas/capturar.py docs/capturas
```

Si el Clínico cae al respaldo determinístico, el script repite el análisis hasta 3 veces y, si sigue
degradado, omite esa captura en vez de guardar un resultado que no refleja al modelo.
