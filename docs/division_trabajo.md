Integrante A — Orquestador + Agente Monitor
orchestrator/graph.py — reemplazar los stubs por los agentes reales a medida que C y B entregan sus módulos. Mantener el guardrail, el nodo condicional y la memoria.
orchestrator/router.py — reemplazar la lógica simple de routing por la clasificación via LLM del Orquestador real.
orchestrator/state.py — custodiar el archivo, cualquier cambio lo coordina con el grupo.
agents/monitor.py — implementar el Agente Monitor real (agente ReAct) conectando las tools de C al LLM via LangChain; el LLM elige la ventana temporal (TimeRange) y el foco de métricas.
tools/threshold_tools.py — [HECHO con C] detect_threshold_violations() con los umbrales ADA como constantes (ADA_THRESHOLDS), hiper e hipoglucemia.

Integrante B — RAG pipeline + datos sintéticos + MongoDB
rag/ingest.py — descarga de PDFs de guías clínicas, chunking, embeddings con nomic-embed-text, indexación en ChromaDB.
rag/retriever.py — implementar search_clinical_guidelines() y get_rag_fragment().
data/generate_patients.py — generar CSVs sintéticos con perfiles clínicamente realistas: paciente controlado, tendencia ascendente, episodio de hipoglucemia, datos insuficientes. Una fila por mes, 12 meses de historial.
Configuración de MongoDB — definir el schema del documento de paciente en JSONB, levantar instancia local (Docker es lo más simple) y poblarla con los datos sintéticos.
tools/rag_tools.py — exponer search_clinical_guidelines() y get_rag_fragment() como tools invocables por LangChain.

Integrante C — Tools del Monitor + Agente Clínico
tools/patient_tools.py — [HECHO] load_patient_data(), calculate_stats() (devuelve MetricStats con campos clínicamente accionables: last_value/mean/min_value/max_value/delta/direction) y get_medication_schedule(). Invocadas por patient_id + metric + TimeRange; ventaneo único en window_metrics().
tools/threshold_tools.py — [HECHO con A] interfaz de detect_threshold_violations() ratificada (por patient_id + metric + timerange; recibe dates en el núcleo).
agents/clinical.py — implementar el Agente Clínico con sus dos modos (reporte y seguimiento), conectando las tools de MongoDB y RAG.
tools/patient_tools.py — también get_patient_history(), compare_with_previous_sessions() y update_patient_history() que operan sobre MongoDB.

Integrante D — Interfaz + observabilidad + evaluación
interface/app.py — Gradio (decisión del equipo, no Streamlit): selector de paciente, campo de contexto clínico del médico, input de consulta, visualización del reporte, historial de conversación, botón de confirmación para guardar sesión.
interface/components.py — componentes reutilizables: tabla de alertas, visualización de tendencias (MetricStats.direction + extremos min/max), badge de severidad.
interface/logging_config.py — configuración de LangSmith y logging propio en JSON.
tests/test_tools.py — validación determinística de todas las tools: mismo input, mismo output esperado.
tests/cases/ — definir los 10 casos de prueba en JSON cubriendo happy path, casos límite y adversariales.

Puntos de coordinación críticos:
A y C tienen que estar sincronizados permanentemente — A integra en el grafo lo que C implementa en los agentes. Cualquier cambio en la firma de una tool lo coordinan los dos antes de commitear.
B desbloquea a C — C no puede terminar get_patient_history() ni compare_with_previous_sessions() hasta que B tenga MongoDB levantado con datos. La prioridad de B la primera semana es tener el schema de MongoDB y los datos sintéticos listos antes que el RAG.
D puede trabajar completamente independiente hasta la semana de integración — arma Streamlit con datos mockeados y lo conecta al grafo real cuando A confirme que el flujo completo corre.

Una consideración sobre C:
C tiene demasiado scope si lo comparás con D. tools/patient_tools.py tiene 5 funciones, más el Agente Clínico completo con dos modos. Si el tiempo aprieta, compare_with_previous_sessions() y update_patient_history() pueden pasarse a B ya que operan sobre MongoDB y B ya está trabajando con esa base.