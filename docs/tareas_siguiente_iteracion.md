# Tareas — siguiente iteración (hacia la 2ª entrega, 22/06)

> Estado base: el **esqueleto del grafo ya corre end-to-end con stubs**
> (`orchestrator/graph.py` + `router.py`, 7 tests pasando). El objetivo de esta iteración
> es reemplazar los stubs por módulos reales **sin romper el repo**, trabajando en paralelo.
>
> **Hito objetivo de la semana:** primera *rebanada vertical real* → el pipeline
> `Monitor → Clínico` produce un `MonitorAnalysis` real sobre datos sintéticos (el RAG del
> Clínico puede venir después).

---

## ⚠️ Camino crítico

```
B (datos + MongoDB)  ──►  C (tools del Monitor)  ──►  A (Monitor real en el grafo)
```

**B es el cuello de botella**: sin CSVs sintéticos y MongoDB cargado, C no puede terminar
sus tools y A no puede reemplazar el stub del Monitor. **Prioridad #1 de la semana = B.**

D trabaja 100% en paralelo (mocks) hasta la semana de integración.

---

## 🔗 Contratos compartidos (acordar ANTES de implementar)

Estos tres contratos se definen primero y se congelan; cualquier cambio se coordina en grupo:

1. **Schema del CSV del EHR** (B produce ↔ C consume en `load_patient_data`). Debe mapear a
   `PatientMetrics` en [orchestrator/state.py](../orchestrator/state.py): `dates`,
   `glucose_fasting`, `hba1c`, `glucose_postprandial`, `weight`,
   `blood_pressure_systolic`, `blood_pressure_diastolic`. Una fila por mes, 12 meses.
2. **Schema del documento de paciente en MongoDB** (B define ↔ C lee/escribe). Mapea a
   `patient_history` (dict) y a lo que escribe `update_patient_history`: datos demográficos,
   diagnósticos, comorbilidades, medicación base, y arreglo de sesiones (fecha, contexto,
   hallazgos del Monitor, interpretación del Clínico, alertas, preguntas sugeridas).
3. **Firmas de las tools** en `tools/*.py` (A integra ↔ C/B implementan). Type hints +
   docstrings devolviendo los modelos de `state.py`. Las firmas de referencia están en la
   sección 2.6 de [TP_2.1 Definicion Conceptual.md](TP_2.1%20Definicion%20Conceptual.md).

> Mientras no estén los contratos, C puede avanzar la lógica de cálculo contra un CSV de
> ejemplo y A puede avanzar el routing por LLM (no dependen de datos reales).

---

## Integrante A — Orquestador + Agente Monitor

**Objetivo:** que el grafo ejecute el Monitor real y que el routing lo decida un LLM.

- [ ] Acordar con C las **firmas de las tools** del Monitor (contrato #3).
- [ ] `orchestrator/router.py` — reemplazar la heurística (`is_followup_message`, etc.) por
      **clasificación vía LLM** del Orquestador (Groq). Mantener las funciones actuales como
      fallback determinístico.
- [ ] `agents/monitor.py` — implementar el Agente Monitor real: LLM (LangChain) + `bind`
      de las tools de C, siguiendo el `MONITOR_SYSTEM_PROMPT` de
      [agents/prompts.py](../agents/prompts.py). Devuelve un `MonitorAnalysis` validado.
- [ ] `orchestrator/graph.py` — reemplazar `monitor_node` (stub) por el agente real.
      **Preservar**: guardrail de 3 iteraciones, nodo condicional (`decide_next`), memoria
      (`MemorySaver`) y la señal `information_sufficient` del loop de refinamiento.
- [ ] `tools/threshold_tools.py` — junto con C, `detect_threshold_violations()` con los
      umbrales ADA como constantes (tabla en sección 2.6 de la def. conceptual).
- [ ] Custodiar [orchestrator/state.py](../orchestrator/state.py): cualquier cambio de campo
      se coordina con el grupo.

**Sincronización:** permanente con C (A integra lo que C implementa).

---

## Integrante B — RAG + datos sintéticos + MongoDB

**Objetivo (prioridad de la semana):** datos + MongoDB listos para desbloquear a C.

- [ ] `data/generate_patients.py` — generar CSVs sintéticos con **4 perfiles clínicamente
      realistas**: (1) paciente controlado, (2) tendencia ascendente, (3) episodio de
      hipoglucemia, (4) datos insuficientes. Una fila por mes, 12 meses de historial.
      Respetar el schema del contrato #1.
- [ ] **MongoDB** — definir el schema del documento de paciente (contrato #2), levantar
      instancia local (Docker es lo más simple) y **poblarla** con los datos sintéticos.
- [ ] `rag/ingest.py` — descarga de PDFs de guías (ADA, SAD, MSAL), chunking, embeddings con
      `nomic-embed-text` (Ollama), indexación en ChromaDB.
- [ ] `rag/retriever.py` — `search_clinical_guidelines()` y `get_rag_fragment()`.
- [ ] `tools/rag_tools.py` — exponer las anteriores como tools invocables por LangChain.

**Orden recomendado:** datos + Mongo **primero** (semana 1), RAG después.

---

## Integrante C — Tools del Monitor + Agente Clínico

**Objetivo:** tools determinísticas del Monitor (rebanada vertical) y luego el Clínico.

- [ ] `tools/patient_tools.py` — `load_patient_data()`, `calculate_stats()` (devuelve
      `MetricStats`), `get_medication_schedule()` (devuelve `list[Medication]`).
      *Se puede arrancar con un CSV de ejemplo antes de que B termine.*
- [ ] `tools/threshold_tools.py` — con A, definir la interfaz de
      `detect_threshold_violations()` (devuelve `list[Alert]`).
- [ ] `tools/patient_tools.py` (sobre MongoDB) — `get_patient_history()`,
      `compare_with_previous_sessions()`, `update_patient_history()`.
      *Bloqueado por B (necesita Mongo con datos).*
- [ ] `agents/clinical.py` — Agente Clínico con sus **dos modos** (reporte y seguimiento),
      siguiendo `CLINICAL_SYSTEM_PROMPT`. Conecta tools de MongoDB y RAG. Debe **setear
      `information_sufficient`** (False cuando falten datos → dispara el loop de refinamiento).

> **Si el tiempo aprieta:** `compare_with_previous_sessions()` y `update_patient_history()`
> pueden pasar a **B** (operan sobre MongoDB, donde B ya trabaja).

**Sincronización:** permanente con A (firmas de tools antes de commitear).

---

## Integrante D — Interfaz + observabilidad + evaluación

**Objetivo:** trabajable de forma 100% independiente con mocks hasta la integración.

- [ ] `interface/app.py` — Streamlit: selector de paciente, campo de contexto clínico del
      médico, input de consulta, visualización del reporte, historial de conversación,
      botón de confirmación para guardar sesión. Empezar con **datos mockeados**.
- [ ] `interface/components.py` — componentes reutilizables: tabla de alertas, visualización
      de tendencias, badge de severidad.
- [ ] `interface/logging_config.py` — LangSmith + logging propio en JSON (requerido por la
      2ª entrega: logging de llamadas al LLM y de invocaciones a tools).
- [ ] `tests/test_tools.py` — validación **determinística** de todas las tools (mismo input,
      mismo output esperado).
- [ ] `tests/cases/*.json` — los **10 casos de prueba**: happy path, casos límite y
      adversariales (los archivos ya existen vacíos).

**Integración:** conectar Streamlit al grafo real cuando A confirme que el flujo completo
corre.

---

## Definición de "hecho" para la 2ª entrega (22/06)

El enunciado exige **esqueleto ejecutable + logging básico + tools/RAG integradas**.
Mínimo para llegar bien:

- [ ] Pipeline `Monitor → Clínico` corriendo sobre datos sintéticos (rebanada vertical).
- [ ] Al menos 2–3 tools funcionales y validadas determinísticamente (C + D).
- [ ] Logging de llamadas al LLM y a tools (D).
- [ ] MongoDB con datos cargados (B).
- [ ] Decisiones de diseño documentadas y sincronizadas con la def. conceptual.

---

## Coordinación crítica (recordatorio)

- **A ↔ C** sincronizados permanentemente: cualquier cambio de firma de tool se acuerda
  entre los dos antes de commitear.
- **B desbloquea a C**: prioridad de B = schema de Mongo + datos sintéticos **antes** que el RAG.
- **D independiente** hasta la semana de integración.
- **`orchestrator/state.py` es archivo custodiado por A**: contrato compartido, no se toca
  sin avisar al grupo.
