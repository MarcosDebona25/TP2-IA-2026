# Estado del Proyecto TP2-IA — Análisis al 26/06/2026

> **Contexto:** La 2ª entrega (22/06) ya pasó. La **entrega final es el 29/06** (en 3 días).
> El backend está completo y el pipeline corre end-to-end con agentes reales. Lo único
> pendiente con peso de entrega es el harness de evaluación (`tests/cases/*.json`).

---

## 📊 Resumen rápido por integrante

| Integrante | Responsabilidad | Progreso | Bloqueante |
|---|---|---|---|
| **A** | Orquestador + Monitor agéntico | 🟢 ~90% | Ninguno. Falta solo (opcional) router por LLM y el nodo de persistencia `save`. |
| **B** | RAG + Datos + MongoDB | 🟢 ~100% | Ninguno. RAG (ingest+retriever), MongoDB (schema+carga, **Docker y local**) y datos sintéticos en `main`. |
| **C** | Tools Monitor + Clínico | 🟢 ~95% | Ninguno. Agente Clínico real conectado a Mongo+RAG reales. |
| **D** | Interfaz + Observabilidad + Evaluación | 🟢 ~85% | Falta solo poblar `tests/cases/*.json` (los 10 casos). |

---

## 🧰 Entorno y dependencias (cómo correr el proyecto)

Todo el stack de **Python** lo gestiona **uv** desde `pyproject.toml` (`uv sync`): incluye
`langchain`, `langgraph`, `langchain-groq`, `chromadb`, `pymongo`, `gradio`, `pydantic`,
`ollama` (cliente), etc. **No hace falta instalar paquetes a mano.**

| Programa / servicio | ¿Cuándo se necesita? | Estado típico |
|---|---|---|
| **uv** | Siempre (entorno + dependencias). | Instalado en `C:\Users\marco\.local\bin`. |
| **Groq API key** | Modo completo (agentes ReAct reales). | En `.env` (`GROQ_API_KEY`). |
| **MongoDB** (Docker o local) | Modo completo (historial de pacientes). | Ver abajo: **Docker Compose** o local nativo. |
| **Ollama** + `nomic-embed-text` | Modo completo (embeddings del RAG / ChromaDB). | **Externo**: instalar desde ollama.com y `ollama pull nomic-embed-text`. |
| **ChromaDB** | Modo completo (vector store de guías). | Lib Python (vía `uv`); persiste en `data/chroma_db/`. Requiere Ollama para indexar. |

- **Modo básico** (sin servicios externos): solo `uv`. El grafo cae a fallbacks
  determinísticos y la UI corre sobre el fixture `data/sample/`. Ideal para verificar que
  arranca. Ver *Inicio rápido* en el [README](../README.md).
- **Modo completo**: `uv` + Groq + MongoDB + Ollama (embeddings) + ChromaDB indexado.

### MongoDB: Docker Compose **o** local nativo

El historial de pacientes vive en MongoDB (`mongodb://localhost:27017`, db `tp2_diabetes`,
colección `patients`). Hay dos formas de levantarlo, intercambiables (el código no cambia):

- **Docker Compose (recomendado).** Con Docker Desktop abierto:
  ```bash
  docker compose -f docker/docker-compose.yml up -d   # levanta mongo:7 (contenedor tp2-mongo)
  uv run python data/load_mongo.py                     # carga P001–P004
  ```
  Persiste en el volumen `tp2-mongo-data` y crea la base + índice vía `docker/mongo-init.js`.
  Comandos completos en [docker/README.md](../docker/README.md).
- **Local nativo (sin Docker).** Iniciar el `mongod` de una instalación local en el puerto
  27017 (en Windows, con `--setParameter diagnosticDataCollectionEnabled=false` para evitar
  crashes). Ver la sección *Modo completo → MongoDB* del [README](../README.md).

> En Windows, `MONGO_URI=mongodb://127.0.0.1:27017` (ya viene en `.env`/`.env.example`)
> evita demoras por la resolución IPv6 de `localhost`. Si MongoDB no está disponible, las
> tools de Mongo degradan con gracia (historial vacío) y el pipeline sigue corriendo.

---

## 🔍 Estado detallado por integrante (verificado contra el código)

### Integrante A — Orquestador + Agente Monitor

| Archivo | Estado | Detalle |
|---|---|---|
| state.py | ✅ Hecho | Modelos Pydantic completos (`AgentState`, `PatientMetrics`, `Alert`, `MonitorAnalysis`, `MetricStats`, `Medication`, `TimeRange`, etc.). Contrato compartido custodiado. |
| graph.py | ✅ Hecho | Grafo end-to-end con Monitor y Clínico **reales** (ReAct) + fallbacks determinísticos sin API key. Loop de refinamiento (guardrail 3 iteraciones). |
| router.py | 🟡 Heurística | Routing por keywords. **Opcional**: reemplazar por clasificación vía LLM (queda heurística como fallback). |
| prompts.py | ✅ Hecho | System + human prompts de los 3 agentes. |
| monitor.py | ✅ Hecho | Agente Monitor ReAct (ChatGroq + 4 tools LangChain), ensambla `MonitorAnalysis`. |
| threshold_tools.py | ✅ Hecho (con C) | Umbrales ADA, hiper **e** hipoglucemia. |

**Lo que falta de A (no bloqueante):**
1. ⬜ Router por LLM en `orchestrator/router.py` (opcional).
2. ⬜ **Nodo de persistencia (`save`)** — ver nota dedicada abajo.

> [!NOTE]
> **Estado de "Guardar sesión" (botón de la UI).** Al confirmar el guardado, hoy el grafo
> enruta a la rama `save`, que **termina en `END` sin escribir nada** ([graph.py](../orchestrator/graph.py),
> `route_from_orchestrator` → `"save": END`). Por eso la UI avisa que la persistencia "todavía
> no está activa".
>
> **Reparto del trabajo (para que quede claro de quién es):**
> - La **tool de escritura** `tools/mongo_tools.update_patient_history` **ya está implementada**
>   (la entregó B/C, opera sobre MongoDB real). **No es un pendiente.**
> - Lo único que falta es **cablear el nodo `save`** en `orchestrator/graph.py` para que llame a
>   esa tool con el reporte, las alertas y el `metrics_summary` de la sesión, y luego termine.
>   Eso es **trabajo del Orquestador (Integrante A)**, no de B ni de D. Marcado con `TODO` en el
>   código ([graph.py](../orchestrator/graph.py), en `route_from_orchestrator`).

---

### Integrante B — RAG + Datos + MongoDB

| Archivo | Estado | Detalle |
|---|---|---|
| generate_patients.py | ✅ Hecho | 4 perfiles sintéticos (P001–P004) en CSV. |
| ingest.py | ✅ Hecho | Chunking + embeddings `nomic-embed-text` (Ollama) → ChromaDB en `data/chroma_db/`. Ingesta por lotes (batches de 50), < 30 s. |
| retriever.py | ✅ Hecho | `search_clinical_guidelines()` y `get_rag_fragment()`. |
| rag_tools.py | ✅ Hecho | Wrappers LangChain (`search_clinical_guidelines_tool`, `get_rag_context_tool`). |
| mongo_tools.py | ✅ Hecho | `get_patient_history`, `compare_with_previous_sessions`, `update_patient_history` sobre MongoDB real, con degradación si Mongo no está disponible. |
| MongoDB (infra) | ✅ Hecho | **Docker Compose** (`docker/docker-compose.yml`, contenedor `tp2-mongo`, volumen persistente, init script) **y** local nativo. `data/load_mongo.py` carga `tp2_diabetes.patients`. |

**Lo que falta de B:** nada bloqueante. El modo completo requiere MongoDB, Ollama y la
ingesta de ChromaDB levantados (ver sección de entorno y README).

---

### Integrante C — Tools del Monitor + Agente Clínico

| Archivo | Estado | Detalle |
|---|---|---|
| patient_tools.py | ✅ Hecho | `load_patient_data`, `calculate_stats`, `get_medication_schedule`, `window_metrics`, `_compute_stats`. Determinístico sobre el EHR. |
| threshold_tools.py | ✅ Hecho (con A) | Completo. |
| clinical.py | ✅ Hecho | Agente Clínico ReAct (modos Reporte y Seguimiento), conectado a `tools/mongo_tools.py` y `rag/retriever.py` reales (stubs eliminados). |

**Lo que falta de C:** nada bloqueante. Recomendado: validar el Clínico end-to-end con
MongoDB + ChromaDB reales levantados.

---

### Integrante D — Interfaz + Observabilidad + Evaluación

| Archivo | Estado | Detalle |
|---|---|---|
| logging_config.py | ✅ Hecho | `setup_logging()` + `LoggingCallbackHandler`, dual output (consola + `logs/agent.jsonl`). Captura `llm_*`/`tool_*` (tokens + nombre de tool). |
| app.py | ✅ Hecho | UI Gradio: **Consulta clínica** (perfil, contexto, análisis, reporte, alertas/tendencias, chat de seguimiento) y **Observabilidad (dev)** (visor de log + JSON crudo). |
| components.py | ✅ Hecho | Funciones puras de render (`severity_badge`, `alerts_table`, `trends_view`, `patient_profile`, `format_report`, `list_patients`, `load_log_entries`). |
| test_tools.py | ✅ Hecho | Tests de integración (`@pytest.mark.integration`) de mongo_tools y RAG; requieren MongoDB + Ollama + ChromaDB. |
| test_graph.py / test_monitor_tools.py | ✅ Hecho (A/C) | Routing/grafo + tools del Monitor. Ver caveat de `test_refinamiento_loop_insuficiente` abajo. |
| `tests/cases/*.json` (×3) | ⬜ **VACÍOS** (0 bytes) | Los 10 casos de prueba (happy/edge/adversarial). **Único pendiente con peso de entrega.** |

**Lo que falta de D:**
1. ⬜ Poblar `tests/cases/happy_path.json`, `edge_cases.json`, `adversarial.json` con los 10 casos.

> [!NOTE]
> **Caveat A↔D:** el fixture `data/sample/P004.csv` (1 fila = "datos insuficientes") hace
> que `test_graph.py::test_refinamiento_loop_insuficiente` falle con `GROQ_API_KEY`: el
> Clínico real considera 1 fila como información suficiente (`iteration=1`, no entra al
> loop). La detección real de "datos insuficientes" en el agente (no solo en el fallback)
> queda como pendiente de A/C.

---

## ✅ Cómo verificar el estado actual

```bash
uv sync                              # entorno (147 paquetes; idempotente)
uv run pytest -m "not integration"   # esperado: 45 passed, 7 deselected
uv run python -m interface.app       # UI en http://127.0.0.1:7860
```

Para el modo completo, además: `.env` con `GROQ_API_KEY`, MongoDB arriba (Docker o local) +
`uv run python data/load_mongo.py`, Ollama con `nomic-embed-text` + `uv run python rag/ingest.py`,
y luego `uv run pytest -m integration`.

---

## 🎯 Siguientes pasos prioritarios para el 29/06

| # | Tarea | Resp. | Prioridad |
|---|---|---|---|
| 1 | Poblar `tests/cases/*.json` (10 casos happy/edge/adversarial) | D | 🔴 Alta |
| 2 | Resolver `test_refinamiento_loop_insuficiente` (detección "datos insuficientes" en el agente) | A/C | 🟡 Media |
| 3 | Nodo de persistencia `save` → `update_patient_history` | A | 🟡 Media |
| 4 | Router por LLM en `router.py` (queda heurística como fallback) | A | 🟢 Baja (opcional) |

---

## ⏰ Resumen de riesgos para el 29/06

| Riesgo | Severidad | Mitigación |
|---|---|---|
| **Casos de prueba (`tests/cases/*.json`) vacíos** | 🟡 Media | Único entregable pendiente; el backend y la UI ya están listos para alimentarlos. |
| **Modo completo no reproducible en otra máquina** | 🟢 Bajo | Mitigado: MongoDB vía Docker Compose (`docker/`), `uv sync` para deps, README con pasos de Ollama/ChromaDB. |
| **Pipeline no corre sin infraestructura** | 🟢 Resuelto | El modo básico corre 100% con fallbacks determinísticos; las tools de Mongo degradan con gracia. |
