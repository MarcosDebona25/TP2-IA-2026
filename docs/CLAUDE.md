# CLAUDE.md

Guía para trabajar en este repositorio. Léela antes de tocar código.

## Qué es

Sistema **multi-agente de soporte clínico** para seguimiento de pacientes con diabetes
tipo 2 (TP2 de Inteligencia Artificial 2026). No emite diagnósticos: produce reportes de
soporte a la decisión médica. Tres agentes coordinados sobre LangGraph:

- **Orquestador** — enruta por inferencia de intención y gestiona el loop de refinamiento.
- **Monitor** — análisis cuantitativo con tools determinísticas (stats, umbrales ADA).
- **Clínico** — interpreta hallazgos con RAG sobre guías clínicas + historial del paciente.

Documentos fuente: [docs/TP_2 Agente.md](docs/TP_2%20Agente.md) (enunciado) y
[docs/TP_2.1 Definicion Conceptual.md](docs/TP_2.1%20Definicion%20Conceptual.md) (diseño).
La definición conceptual es la fuente de verdad del diseño; mantenerla sincronizada con el
código.

## Stack y comandos

- **uv** gestiona el entorno (instalado en `C:\Users\marco\.local\bin`; en terminales
  nuevas ya está en el PATH).
- LLM: Groq `llama-3.3-70b` · Embeddings: Ollama `nomic-embed-text` · Vector store:
  ChromaDB (solo guías) · Historial: **MongoDB** documental · Validación: Pydantic v2 ·
  Interfaz: Streamlit · Observabilidad: LangSmith.

```bash
uv sync                 # instalar/actualizar entorno
uv run pytest           # correr la suite (config en pyproject: pythonpath=["."], testpaths=["tests"])
uv lock                 # regenerar lockfile tras cambiar dependencias
```

## Arquitectura del código

- [orchestrator/state.py](orchestrator/state.py) — `AgentState` (TypedDict del grafo) y
  modelos Pydantic: `PatientMetrics`, `Alert`, `MonitorAnalysis`, `Medication`,
  `MetricStats`, `BloodPressureStats`, `CGMMetrics`. **Archivo custodiado**: coordinar
  cualquier cambio con el grupo (es contrato compartido entre todos los nodos).
- [orchestrator/graph.py](orchestrator/graph.py) — grafo LangGraph. Hoy con **nodos stub**.
  Entry en `orchestrator`; `monitor → clinical`; loop de refinamiento `clinical → monitor`.
- [orchestrator/router.py](orchestrator/router.py) — lógica de routing (heurística por
  ahora; reemplazar por clasificación vía LLM).
- [agents/prompts.py](agents/prompts.py) — system + human prompts de los 3 agentes.
- `agents/`, `tools/`, `rag/`, `interface/`, `data/` — **mayormente vacíos** (pendientes).

## Decisiones de diseño (no revertir sin discutir)

1. **Routing por inferencia de intención**, no por skills `/monitor` `/clinico`. El
   Orquestador lee `state["query"]` + estado y decide: pipeline completo / seguimiento
   directo al Clínico / reset / confirmación / aclaración.
2. **Historial del paciente en MongoDB** (documento por paciente, búsqueda exacta por id,
   **sin RAG**). RAG es exclusivo de las guías clínicas.
3. **CGM = extensión futura/opcional**. `CGMMetrics`/`cgm_series` están definidos pero
   fuera del alcance de la implementación actual; marcado así en la def. conceptual.
4. **Loop de refinamiento**: el Clínico expone `information_sufficient`; si es `False` e
   `iteration < 3`, el grafo vuelve al Monitor (`decide_next`). Guardrail = 3 iteraciones.
   El contador se reinicia en el Orquestador en cada mensaje nuevo (por eso el loop NO
   vuelve por el nodo orquestador, para no resetear `iteration`).
5. **Modelos tipados** en vez de `dict`/`list[str]`: `Medication`, `MetricStats`,
   `BloodPressureStats`.
6. **Memoria de sesión** vía `MemorySaver` (checkpointer): toda invocación requiere
   `config={"configurable": {"thread_id": ...}}`.

## Convenciones

- Match el estilo del código circundante; comentarios y prompts en español.
- Los stubs llevan `TODO:` indicando con qué se reemplazan.
- Toda salida clínica incluye el disclaimer obligatorio (ver `prompts.py`).
- Las tools del Monitor son **determinísticas**; validarlas con tests determinísticos.

## Estado de implementación (al 2026-06-13)

| Módulo | Estado |
|---|---|
| `state.py`, `prompts.py` | ✅ completos y verificados |
| `graph.py`, `router.py` | ✅ esqueleto funcional con stubs (corre end-to-end) |
| `tests/test_graph.py` | ✅ 7 tests pasando |
| `pyproject.toml`, entorno uv | ✅ deps y entorno listos |
| Tools (`tools/*.py`) | ⬜ vacíos |
| Agentes reales (`agents/monitor.py`, `clinical.py`) | ⬜ vacíos |
| RAG (`rag/*.py`), datos (`data/generate_patients.py`) | ⬜ vacíos |
| MongoDB (schema + instancia + carga) | ⬜ pendiente |
| Interfaz (`interface/*.py`), observabilidad | ⬜ vacíos |
| `tests/test_tools.py`, `tests/cases/*.json` | ⬜ vacíos |

## División de trabajo

Ver [docs/division_trabajo.md](docs/division_trabajo.md). Resumen:

- **A — Orquestador + Monitor**: `graph.py` (reemplazar stubs por agentes reales
  manteniendo guardrail/condicional/memoria), `router.py` (LLM), custodia de `state.py`,
  `agents/monitor.py`, `tools/threshold_tools.py`.
- **B — RAG + datos + MongoDB**: `rag/ingest.py`, `rag/retriever.py`,
  `data/generate_patients.py`, schema e instancia de MongoDB, `tools/rag_tools.py`.
- **C — Tools del Monitor + Clínico**: `tools/patient_tools.py` (5 funciones),
  `agents/clinical.py` (modos reporte y seguimiento).
- **D — Interfaz + observabilidad + evaluación**: `interface/*.py`,
  `tests/test_tools.py`, `tests/cases/*.json` (10 casos).

Coordinación crítica:
- **A ↔ C** sincronizados: A integra en el grafo lo que C implementa; cualquier cambio de
  firma de una tool se coordina antes de commitear.
- **B desbloquea a C**: prioridad de B la primera semana = schema de MongoDB + datos
  sintéticos antes que el RAG.
- **D independiente** hasta la integración (Streamlit con mocks, luego conecta al grafo).
- Si C va sobrecargado, `compare_with_previous_sessions()` y `update_patient_history()`
  pueden pasar a B (operan sobre MongoDB).

## Próximos pasos

1. Reemplazar los nodos stub de `graph.py` por los agentes reales a medida que B y C
   entregan (responsable A), preservando guardrail, condicional y memoria.
2. Agregar el nodo de persistencia: rama `save` → `update_patient_history` (hoy `save`
   termina en `END`).
3. Reemplazar la heurística de `router.py` por clasificación vía LLM.
4. Implementar tools, RAG, MongoDB, interfaz y los casos de prueba (5–15) con logging.
```
