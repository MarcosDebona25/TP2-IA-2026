# Estado del Proyecto TP2-IA — Análisis al 19/06/2026

> **Contexto:** La 2ª entrega es el **22/06** (en 3 días). La entrega final es el **29/06** (en 10 días).

---

## 📊 Resumen rápido por integrante

| Integrante | Responsabilidad | Progreso | Bloqueante |
|---|---|---|---|
| **A** | Orquestador + Monitor agéntico | 🟢 ~85% | Ninguno (Grafo completo con agentes reales e integración ReAct listos) |
| **B** | RAG + Datos + MongoDB | 🔴 ~5% | **Cuello de botella crítico** — todo vacío |
| **C** | Tools Monitor + Clínico | 🟢 ~80% | Ninguno (Agente Clínico real con tools stubs de Mongo y RAG listo) |
| **D** | Interfaz + Observabilidad + Evaluación | 🟢 ~70% | Falta solo el harness de evaluación: `test_tools.py` + `tests/cases/*.json` (Fragmento 3) |

---

## 🔍 Estado detallado por integrante (verificado contra el código)

### Integrante A — Orquestador + Agente Monitor

| Archivo | Estado | Detalle |
|---|---|---|
| state.py | ✅ Hecho | Modelos Pydantic completos (`AgentState`, `PatientMetrics`, `Alert`, `MonitorAnalysis`, `MetricStats`, `Medication`, `TimeRange`, etc.) |
| graph.py | ✅ Hecho | El grafo corre end-to-end con agentes reales (Monitor y Clínico) e incluye fallbacks determinísticos si no hay API key de Groq. |
| router.py | 🟡 Heurística | `is_followup_message` e `is_confirmation_message` son heurísticas por keywords. **Falta reemplazar por clasificación vía LLM** |
| prompts.py | ✅ Hecho | System + human prompts para los 3 agentes completos |
| monitor.py | ✅ Hecho | Agente Monitor real ReAct completo con vinculación de herramientas clínicas. |
| threshold_tools.py | ✅ Hecho (con C) | `detect_threshold_violations` con umbrales ADA, hiper e hipoglucemia. 133 líneas, completo |
 
**Lo que falta de A:**
1. ⬜ `orchestrator/router.py` — Clasificación por LLM (puede quedar heurística como fallback)

---

### Integrante B — RAG + Datos + MongoDB

| Archivo | Estado | Detalle |
|---|---|---|
| generate_patients.py | ⬜ **VACÍO** (solo un comentario) | `# Implementar integrante B` — 26 bytes |
| ingest.py | ⬜ **VACÍO** (0 bytes) | Descarga PDFs + chunking + embeddings → ChromaDB |
| retriever.py | ⬜ **VACÍO** (0 bytes) | `search_clinical_guidelines()` y `get_rag_fragment()` |
| rag_tools.py | ⬜ **VACÍO** (0 bytes) | Wrappers LangChain de las tools RAG |
| MongoDB | ⬜ No existe | Ni schema, ni instancia, ni datos cargados |

> [!CAUTION]
> **B es el cuello de botella total.** TODO su scope está vacío. Las tools de MongoDB de C están bloqueadas por B, y el RAG del Clínico también. Si B no entrega datos sintéticos y MongoDB **urgente**, el pipeline no puede correr con datos reales para el 22/06.

**Lo que falta de B — TODO:**
1. ⬜ Datos sintéticos (`generate_patients.py`) — 4 perfiles, CSV, 12 meses
2. ⬜ MongoDB — schema, instancia (Docker), carga de datos
3. ⬜ RAG ingest — PDFs de guías + embeddings en ChromaDB
4. ⬜ RAG retriever — `search_clinical_guidelines()`
5. ⬜ RAG tools — wrappers LangChain

---

### Integrante C — Tools del Monitor + Agente Clínico

| Archivo | Estado | Detalle |
|---|---|---|
| patient_tools.py | ✅ Hecho | 223 líneas. `load_patient_data`, `calculate_stats`, `get_medication_schedule`, `window_metrics`, `_compute_stats`. Todo funcional sobre `data/sample/` |
| threshold_tools.py | ✅ Hecho (con A) | Completo |
| clinical.py | ✅ Hecho | Agente Clínico real con loop ReAct (Modos Reporte y Seguimiento) completo. |
| Tools MongoDB (en patient_tools) | 🟡 Stubs | `get_patient_history` y `compare_with_previous_sessions` implementadas como stubs funcionales para datos sintéticos (desbloqueado para 22/06). |

**Lo que falta de C:**
1. ⬜ Conectar MongoDB real una vez que Integrante B provea la base de datos.
2. ⬜ Conectar RAG real (ChromaDB) una vez que Integrante B provea el retriever.

---

### Integrante D — Interfaz + Observabilidad + Evaluación

| Archivo | Estado | Detalle |
|---|---|---|
| logging_config.py | ✅ Hecho | `setup_logging()` + `LoggingCallbackHandler` + dual output (consola + JSONL). Captura `llm_*`/`tool_*` (con tokens y nombre de tool) en el camino real |
| app.py | ✅ Hecho | UI Gradio con 2 pestañas: **Consulta clínica** (selector, perfil, contexto, análisis, reporte panel principal, alertas/tendencias, chat de seguimiento, guardar) y **Observabilidad (dev)** (visor de log con filtro + JSON crudo) |
| components.py | ✅ Hecho | Funciones puras: `severity_badge`, `alerts_table`, `trends_view`, `patient_profile`, `format_report`, `list_patients`, `load_log_entries`, `log_entries_to_rows` |
| test_tools.py | ⬜ **VACÍO** (0 bytes) | Tests determinísticos de todas las tools (Fragmento 3) |
| `tests/cases/*.json` (×3) | ⬜ **VACÍOS** (0 bytes cada uno) | Los 10 casos de prueba (happy/edge/adversarial) (Fragmento 3) |
| test_graph.py | ✅ Hecho (A) | Tests de routing/grafo. ⚠️ `test_refinamiento_loop_insuficiente` falla con el fixture P004 (ver nota abajo) |
| test_monitor_tools.py | ✅ Hecho (C) | Tests de patient_tools y threshold_tools. Pasan con el fixture `data/sample/*.csv` |
| data/sample/*.csv | ✅ Hecho (D, provisional) | 4 perfiles P001–P004 (contrato #1) creados por D para destrabar la UI y los tests. Reemplazables por el generador de B |

**Lo que falta de D:**
1. ⬜ `test_tools.py` — test runner con parametrización (Fragmento 3)
2. ⬜ `tests/cases/*.json` — los 10 casos de prueba (Fragmento 3)

> [!NOTE]
> **Nota A↔D:** el fixture `data/sample/P004.csv` (1 fila = "datos insuficientes") hace que
> `test_graph.py::test_refinamiento_loop_insuficiente` falle: con `GROQ_API_KEY`, el Agente Clínico
> real considera que 1 fila es información suficiente (devuelve `iteration=1`, no entra al loop de
> refinamiento). Antes pasaba "de casualidad" porque P004 no tenía CSV y el análisis quedaba vacío.
> La detección real de "datos insuficientes" en el agente (no solo en el fallback) es de A/C.

---

## 🎯 Siguientes Pasos Prioritarios para el Equipo

Tras completar la integración de los agentes Monitor y Clínico reales, el equipo debe enfocarse en los siguientes objetivos antes de la entrega del **22/06**:

### Plan de acción concreto (priorizado):

#### 🔴 Prioridad 1: Implementar la UI Completa e integrar Componentes (Integrante D)
* Diseñar y rellenar `interface/components.py` (`severity_badge`, `alerts_table`, `trends_view`, `patient_profile`, `format_report`).
* Integrar estos componentes en `interface/app.py` para tener una visualización rica de los datos estructurados del estado.

#### 🔴 Prioridad 2: Diseñar y cargar Casos de Prueba (Integrante D)
* Completar los archivos JSON en `tests/cases/*.json` para cubrir los 10 casos de prueba (happy/edge/adversariales) definidos conceptualmente.

#### 🟡 Prioridad 3: Router por LLM (Integrante A)
* Reemplazar la heurística basada en palabras clave en `orchestrator/router.py` por clasificación vía LLM usando `ChatGroq` y `ORCHESTRATOR_SYSTEM_PROMPT`.

#### 🟡 Prioridad 4: Conectar MongoDB y RAG reales en cuanto B entregue (Integrante C + B)
* Integrante B debe proveer la base de datos MongoDB cargada con los datos sintéticos de `generate_patients.py`.
* Integrante B debe proveer el ingestion y retriever de ChromaDB.
* Integrante C reemplazará los stubs clínicos por consultas reales a MongoDB y ChromaDB.

---

## ⏰ Resumen de riesgos para el 22/06

| Riesgo | Severidad | Mitigación |
|---|---|---|
| **B no entrega datos ni MongoDB a tiempo** | 🟡 Media (Antes Alta) | **Mitigado:** A+C implementaron stubs realistas de base de datos y guías clínicas. La "rebanada vertical" corre 100% agéntica y determinística sin MongoDB ni ChromaDB. |
| **Pipeline no corre end-to-end con agentes reales** | 🟢 Resuelto | **Logrado:** Monitor y Clínico ya corren como agentes ReAct reales integrados en el grafo, pasando las pruebas unitarias y de integración correspondientes. |
| **Componentes de UI y casos de prueba vacíos (D)** | 🔴 Alta | D debe enfocar sus esfuerzos en `interface/components.py`, `interface/app.py` y `tests/cases/*.json` urgentemente, ya que el backend está completamente listo. |

