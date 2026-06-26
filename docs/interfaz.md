# Interfaz de usuario (Gradio)

Interfaz web del sistema, construida con **Gradio**. Conecta al grafo real
([orchestrator/graph.py](../orchestrator/graph.py)); con `GROQ_API_KEY` usa los agentes ReAct,
y sin ella cae a los fallbacks determinísticos.

## Levantarla

```bash
uv run python -m interface.app   # http://127.0.0.1:7860
```

## Archivos

| Archivo | Rol |
|---|---|
| [interface/app.py](../interface/app.py) | Layout, pestañas y wiring de eventos. Invoca el grafo. |
| [interface/components.py](../interface/components.py) | Funciones **puras** de render (Markdown/HTML). Sin Gradio → testeables. |
| [interface/logging_config.py](../interface/logging_config.py) | Observabilidad (ver [docs/logs.md](logs.md)). |

## Pestaña 1 — Consulta clínica

Sigue el flujo de la def. conceptual (§2.4):

1. **Seleccionar paciente** (desplegable). Los IDs salen de los CSV del EHR
   (`data/sample/*.csv`), de forma dinámica: al cambiar el fixture por el dataset real de B,
   el selector se actualiza solo.
2. **Perfil resumido**: registros de EHR, último peso/PA y medicación activa.
3. **Contexto clínico adicional** (opcional): se pasa al estado como `doctor_context`.
4. **Analizar paciente**: ejecuta el pipeline Monitor → Clínico. Resultados:
   - **Reporte clínico** (panel principal).
   - **Alertas detectadas** (tabla con badge de severidad).
   - **Tendencias por métrica** (último, media, mín, máx, Δ, dirección).
5. **Seguimiento** (chat): preguntas sobre el reporte ya generado (van directo al Clínico).
   El Clínico responde **solo** dentro del dominio clínico del paciente; los pedidos ajenos
   (código, temas generales, etc.) se rechazan cortésmente.
6. **Guardar sesión**: confirma la sesión (rama `save` del Orquestador). ⚠️ **La escritura
   real en MongoDB todavía no está cableada**: la rama `save` del grafo termina en `END` sin
   persistir. La tool `tools/mongo_tools.update_patient_history` ya existe; falta conectar el
   nodo `save` en `orchestrator/graph.py` (pendiente del Orquestador, ver `docs/estado_proyecto.md`).

## Pestaña 2 — Observabilidad (dev)

Visor del log estructurado (`logs/agent.jsonl`) para desarrollo, sin salir de la UI:

- Estado de **LangSmith** + enlace al dashboard.
- **Filtro** por tipo de evento (`node` / `routing` / `llm` / `tool`).
- Botón **Refrescar** (el log se llena al usar la pestaña de consulta).
- **JSON crudo** de la traza seleccionada al hacer clic en una fila.

Detalle de los campos y eventos del log: [docs/logs.md](logs.md).

## Datos de muestra

La UI y las tools del Monitor corren sobre el fixture [data/sample/](../data/sample/) (4 perfiles
`P001`–`P004`, ver su README). Es provisional: lo reemplaza el generador real de B al mismo schema
(contrato #1). El selector y el perfil degradan con elegancia si un paciente no tiene CSV.
