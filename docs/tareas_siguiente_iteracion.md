# Tareas — siguiente iteración (hacia la 2ª entrega, 22/06)

> Estado base: el **esqueleto del grafo ya corre end-to-end con stubs**
> (`orchestrator/graph.py` + `router.py`, 7 tests pasando) y la **observabilidad ya está en
> pie** (logging propio dual + LangSmith, traceando los nodos stub — Integrante D). El objetivo
> de esta iteración es reemplazar los stubs por módulos reales **sin romper el repo**, en paralelo.
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
   **Tools del Monitor (EHR/umbrales): RATIFICADO A+C** — por `patient_id` + `metric` +
   `TimeRange`, finas y separadas; refinamientos vs §2.6 en decisiones #7–#9 de
   [CLAUDE.md](../docs/CLAUDE.md). Las tools de Mongo (B) siguen pendientes de definir.

> Mientras no estén los contratos, C puede avanzar la lógica de cálculo contra un CSV de
> ejemplo y A puede avanzar el routing por LLM (no dependen de datos reales).

---

## Integrante A — Orquestador + Agente Monitor

**Objetivo:** que el grafo ejecute el Monitor real y que el routing lo decida un LLM.

- [x] Acordar con C las **firmas de las tools** del Monitor (contrato #3) — **ratificado**:
      tools por `patient_id` + `metric` + `TimeRange`, finas y separadas (§2.6). Ver "Flujo de
      métricas" y decisiones #7–#9 en [CLAUDE.md](../docs/CLAUDE.md).
- [ ] `orchestrator/router.py` — reemplazar la heurística (`is_followup_message`, etc.) por
      **clasificación vía LLM** del Orquestador (Groq). Mantener las funciones actuales como
      fallback determinístico.
- [ ] `agents/monitor.py` — implementar el Agente Monitor real: LLM (LangChain) + `bind` de las
      tools de C (`calculate_stats`, `detect_threshold_violations`, `load_patient_data`,
      `get_medication_schedule`) como `@tool`/`StructuredTool`, siguiendo el
      `MONITOR_SYSTEM_PROMPT`. El LLM elige el `TimeRange` por consulta. Devuelve un
      `MonitorAnalysis` validado.
- [ ] `orchestrator/graph.py` — reemplazar `monitor_node` (stub) por el agente real.
      **Preservar**: guardrail de 3 iteraciones, nodo condicional (`decide_next`), memoria
      (`MemorySaver`) y la señal `information_sufficient` del loop de refinamiento.
- [x] `tools/threshold_tools.py` — `detect_threshold_violations()` con los umbrales ADA como
      constantes (`ADA_THRESHOLDS`, §2.6). **Hecho junto con C** (núcleo + wrapper + tests).
- [ ] Custodiar [orchestrator/state.py](../orchestrator/state.py): cualquier cambio de campo
      se coordina con el grupo. (Esta iteración se agregó `TimeRange`, consensuado A+C.)

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

- [x] `tools/patient_tools.py` — `load_patient_data()` (→ `PatientMetrics`),
      `calculate_stats(patient_id, metric, timerange=None)` (→ `MetricStats`),
      `get_medication_schedule()` (→ `list[Medication]`), `window_metrics()` (ventaneo único).
      **Hecho** contra el fixture `data/sample/` (4 perfiles, contrato #1) y testeado en
      `tests/test_monitor_tools.py`. `MetricStats` simplificado a campos clínicamente
      accionables (`last_value`/`mean`/`min_value`/`max_value`/`delta`/`direction`; se quitaron
      `std` y `trend` crudo). Pendiente: cuando B entregue, apuntar a la fuente real.
- [x] `tools/threshold_tools.py` — `detect_threshold_violations(patient_id, metric,
      timerange=None)` (→ `list[Alert]`) con `ADA_THRESHOLDS` (§2.6). **Hecho y testeado**,
      incluye **detección de hipoglucemia** (banda baja: `<70` moderada, `<54` severa).
      Pendiente futuro: umbrales de objetivo de control (HbA1c <7%) y de peso/presión.
- [x] **Lineamiento de métricas (contrato A+C, RATIFICADO)** — ver "Flujo de métricas" en
      [CLAUDE.md](../docs/CLAUDE.md). Monitor agéntico (LLM razona ventana/foco/loop) + tools
      determinísticas finas y separadas (§2.6), invocadas **por `patient_id`**; `TimeRange`
      (`last_n_months` o `start`/`end`, default global) aplicado solo en `window_metrics`;
      `detect_threshold_violations` recibe `dates` (Alert exige fecha). Decisiones #7–#9 en CLAUDE.md.
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
**Decisión tomada:** se usa **Gradio**, no Streamlit. Plan detallado en
[plan_integrante_D.md](plan_integrante_D.md).

- [x] `interface/logging_config.py` — **hecho**. Logging propio dual (consola legible +
      `logs/agent.jsonl` vía `RotatingFileHandler`) + `LoggingCallbackHandler` que ya tracea
      nodos/routing y registrará `llm_*`/`tool_*` en cuanto existan. LangSmith activo por env
      vars. Guía en [logs.md](logs.md).
- [~] `interface/app.py` — **esqueleto Gradio funcional** que invoca el grafo real con
      `thread_id` por sesión y `callbacks=get_callbacks()`. **Falta:** layout de la def.
      conceptual (reporte como panel principal, selector de paciente, contexto clínico,
      botón guardar) y la pestaña de observabilidad (visor de `logs/agent.jsonl`).
- [ ] `interface/components.py` — componentes/​helpers puros reutilizables: tabla de alertas,
      tendencias, badge de severidad, perfil de paciente, `load_log_entries`. **Vacío aún.**
- [ ] `tests/test_tools.py` — validación **determinística** de todas las tools (mismo input,
      mismo output esperado). Arrancar con `pytest.importorskip` hasta que C/B entreguen.
- [ ] `tests/cases/*.json` — los **10 casos de prueba**: happy path, casos límite y
      adversariales (los archivos ya existen vacíos). Schema acordado en el plan de D.

**Integración:** conectar el resto de la UI Gradio al flujo completo cuando A confirme que
el pipeline real corre (la conexión base al grafo ya existe).

---

## Definición de "hecho" para la 2ª entrega (22/06)

El enunciado exige **esqueleto ejecutable + logging básico + tools/RAG integradas**.
Mínimo para llegar bien:

- [ ] Pipeline `Monitor → Clínico` corriendo sobre datos sintéticos (rebanada vertical).
- [x] Al menos 2–3 tools funcionales y validadas determinísticamente — **hecho**: 3 tools
      del Monitor (`load_patient_data`, `calculate_stats`, `detect_threshold_violations`,
      `get_medication_schedule`) sobre `data/sample/`, 17 tests en `tests/test_monitor_tools.py`.
- [x] Logging de llamadas al LLM y a tools (D) — **infraestructura lista**; emitirá los
      eventos `llm_*`/`tool_*` automáticamente cuando A/B/C conecten LLMs y tools reales.
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
