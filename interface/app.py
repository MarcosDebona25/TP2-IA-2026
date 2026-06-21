# interface/app.py
#
# Interfaz Gradio del sistema multi-agente (tarea del Integrante D).
#
# Dos pestañas:
#   1. "Consulta clínica" — flujo del médico: seleccionar paciente → ver perfil → agregar
#      contexto → analizar → leer el reporte (panel principal) + chat de seguimiento → guardar.
#   2. "Observabilidad (dev)" — visor del log estructurado (logs/agent.jsonl) para desarrollo,
#      con filtro por tipo de evento, refresco y JSON crudo de cada traza.
#
# Conecta al grafo REAL (orchestrator.graph.app): con GROQ_API_KEY usa los agentes ReAct;
# sin ella, el grafo cae a sus fallbacks determinísticos. Los componentes de presentación
# viven en interface/components.py (funciones puras, testeables).

from dotenv import load_dotenv
load_dotenv()

import gradio as gr

from orchestrator.graph import app as langgraph_app
from interface.logging_config import setup_logging, get_callbacks, tracing_status
from interface.components import (
    alerts_table,
    format_report,
    list_patients,
    load_log_entries,
    log_entries_to_rows,
    patient_profile,
    trends_view,
)
from tools.patient_tools import get_medication_schedule, load_patient_data

# Configura el logging propio (consola legible + logs/agent.jsonl) al iniciar.
setup_logging()

_thread_counter = 0


def _new_thread_id() -> str:
    """Nuevo thread_id de sesión para el checkpointer del grafo."""
    global _thread_counter
    _thread_counter += 1
    return f"session-{_thread_counter}"


def _last_assistant(conversation: list[dict]) -> str:
    """Último mensaje del asistente en la conversación acumulada del grafo."""
    for msg in reversed(conversation or []):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return "(sin respuesta)"


def _config(thread_id: str) -> dict:
    """Config de invocación: thread_id de memoria + callbacks de observabilidad."""
    return {"configurable": {"thread_id": thread_id}, "callbacks": get_callbacks()}


# -------------------------------------------------------------------
# Callbacks de la UI — pestaña "Consulta clínica"
# -------------------------------------------------------------------

def on_patient_change(patient_id: str) -> str:
    """Carga el perfil resumido al seleccionar un paciente (paso 2 del flujo)."""
    metrics = meds = None
    if patient_id:
        try:
            metrics = load_patient_data(patient_id)
        except Exception:
            metrics = None
        try:
            meds = get_medication_schedule(patient_id)
        except Exception:
            meds = None
    return patient_profile(patient_id, metrics, meds)


def analyze(patient_id: str, doctor_context: str):
    """Lanza el análisis completo (Monitor → Clínico) sobre un paciente nuevo."""
    if not patient_id:
        aviso = "Seleccioná un paciente antes de analizar."
        return [{"role": "assistant", "content": aviso}], "", format_report(None), alerts_table([]), trends_view(None)

    thread_id = _new_thread_id()
    state_input = {
        "patient_id": patient_id,
        "query": "Realizá un análisis clínico integral del paciente.",
        "doctor_context": doctor_context or "",
        "conversation": [],
    }
    try:
        out = langgraph_app.invoke(state_input, _config(thread_id))
    except Exception as e:
        err = f"⚠️ Error al ejecutar el análisis: {e}"
        return [{"role": "assistant", "content": err}], thread_id, format_report(None), alerts_table([]), trends_view(None)

    analysis = out.get("analysis")
    alerts = analysis.alerts if analysis else []
    chat = [{
        "role": "assistant",
        "content": (
            f"✅ Análisis de **{patient_id}** completado: {len(alerts)} alerta(s). "
            "El reporte está en el panel principal. Hacé tu pregunta de seguimiento abajo."
        ),
    }]
    return chat, thread_id, format_report(out.get("report")), alerts_table(alerts), trends_view(analysis)


def follow_up(message: str, history: list, thread_id: str):
    """Pregunta de seguimiento sobre el reporte ya generado (va directo al Clínico)."""
    message = (message or "").strip()
    if not message:
        return history, ""
    if not thread_id:
        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": "Primero analizá un paciente con **Analizar paciente**."},
        ]
        return history, ""

    try:
        out = langgraph_app.invoke({"query": message}, _config(thread_id))
        reply = _last_assistant(out.get("conversation", []))
    except Exception as e:
        reply = f"⚠️ Error: {e}"

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    return history, ""


def save_session(thread_id: str, history: list):
    """Confirma el guardado de la sesión (rama 'save' del Orquestador)."""
    if not thread_id:
        return history + [{"role": "assistant", "content": "No hay sesión activa para guardar."}]
    try:
        langgraph_app.invoke({"query": "confirmar"}, _config(thread_id))
        msg = "💾 Confirmación recibida. La persistencia en MongoDB se conecta cuando B la provea."
    except Exception as e:
        msg = f"⚠️ Error al guardar: {e}"
    return history + [
        {"role": "user", "content": "confirmar"},
        {"role": "assistant", "content": msg},
    ]


def reset_session():
    """Limpia la sesión para empezar una consulta nueva."""
    return [], "", format_report(None), alerts_table([]), trends_view(None), ""


# -------------------------------------------------------------------
# Callbacks de la UI — pestaña "Observabilidad (dev)"
# -------------------------------------------------------------------

def refresh_logs(event_filter: str):
    """Recarga las trazas del log y las devuelve como filas + entradas crudas."""
    entries = load_log_entries(None if event_filter == "todos" else event_filter)
    return log_entries_to_rows(entries), entries


def show_raw_entry(entries: list, evt: gr.SelectData):
    """Muestra el JSON crudo de la fila seleccionada en la tabla de logs."""
    try:
        return entries[evt.index[0]]
    except Exception:
        return {}


def _langsmith_md() -> str:
    st = tracing_status()
    activo = st["langsmith_enabled"] and st["has_api_key"]
    estado = "✅ activo" if activo else "⚠️ inactivo (sin LANGSMITH_API_KEY o tracing off)"
    proj = st.get("project") or "—"
    return (
        f"**LangSmith:** {estado} · proyecto `{proj}` · "
        "[Abrir dashboard](https://smith.langchain.com)\n\n"
        "Las trazas también se registran localmente en `logs/agent.jsonl` (tabla de abajo)."
    )


# -------------------------------------------------------------------
# Construcción de la UI
# -------------------------------------------------------------------

def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Monitor Clínico — Diabetes") as demo:
        gr.Markdown(
            "# 🩺 Monitor Clínico — Diabetes tipo 2\n"
            "Sistema multi-agente de soporte a la decisión clínica. "
            "_No emite diagnósticos; es un insumo para el médico tratante._"
        )

        thread_state = gr.State("")
        logs_state = gr.State([])

        with gr.Tabs():
            # ---------------- Pestaña 1: Consulta clínica ----------------
            with gr.Tab("Consulta clínica"):
                with gr.Row():
                    patient_dd = gr.Dropdown(
                        choices=list_patients(), label="Paciente", scale=2,
                        info="Datos cargados desde el EHR (data/sample/).",
                    )
                    context_tb = gr.Textbox(
                        label="Contexto clínico adicional (opcional)", scale=3, lines=2,
                        placeholder="Síntomas recientes, eventos intercurrentes, adherencia referida…",
                    )
                    analyze_btn = gr.Button("Analizar paciente", variant="primary", scale=1)

                profile_md = gr.Markdown("_Seleccioná un paciente para ver su perfil._")

                with gr.Row():
                    # Panel principal: reporte clínico
                    with gr.Column(scale=2):
                        gr.Markdown("### Reporte clínico")
                        report_md = gr.Markdown(format_report(None))
                        with gr.Accordion("🔔 Alertas detectadas", open=True):
                            alerts_md = gr.Markdown(alerts_table([]))
                        with gr.Accordion("📈 Tendencias por métrica", open=False):
                            trends_md = gr.Markdown(trends_view(None))

                    # Panel secundario: chat de seguimiento
                    with gr.Column(scale=1):
                        gr.Markdown("### Seguimiento")
                        chatbot = gr.Chatbot(
                            label="Conversación", height=380, buttons=["copy_all"],
                            placeholder="El chat se habilita tras analizar un paciente.",
                        )
                        query_tb = gr.Textbox(
                            show_label=False, submit_btn=True,
                            placeholder="Pregunta de seguimiento sobre el reporte…",
                        )
                        with gr.Row():
                            save_btn = gr.Button("💾 Guardar sesión", variant="secondary")
                            reset_btn = gr.Button("Nueva sesión")

            # ---------------- Pestaña 2: Observabilidad (dev) ----------------
            with gr.Tab("Observabilidad (dev)"):
                langsmith_md = gr.Markdown(_langsmith_md())
                with gr.Row():
                    event_filter_dd = gr.Dropdown(
                        choices=["todos", "node", "routing", "llm", "tool"],
                        value="todos", label="Filtrar por tipo de evento", scale=3,
                    )
                    refresh_btn = gr.Button("🔄 Refrescar", scale=1)
                logs_df = gr.Dataframe(
                    headers=["Hora", "Evento", "Componente", "Resumen"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False, wrap=True, label="Trazas (logs/agent.jsonl)",
                )
                gr.Markdown("_Hacé clic en una fila para ver su JSON crudo:_")
                raw_json = gr.JSON(label="Detalle del evento")

        # ---------------- Wiring de eventos ----------------
        patient_dd.change(on_patient_change, inputs=patient_dd, outputs=profile_md)

        analyze_btn.click(
            analyze,
            inputs=[patient_dd, context_tb],
            outputs=[chatbot, thread_state, report_md, alerts_md, trends_md],
        )

        query_tb.submit(
            follow_up,
            inputs=[query_tb, chatbot, thread_state],
            outputs=[chatbot, query_tb],
        )

        save_btn.click(save_session, inputs=[thread_state, chatbot], outputs=chatbot)

        reset_btn.click(
            reset_session,
            outputs=[chatbot, thread_state, report_md, alerts_md, trends_md, context_tb],
        )

        # Observabilidad: refrescar manual, al cambiar el filtro y al cargar la página.
        for trigger in (refresh_btn.click, event_filter_dd.change, demo.load):
            trigger(refresh_logs, inputs=event_filter_dd, outputs=[logs_df, logs_state])
        logs_df.select(show_raw_entry, inputs=logs_state, outputs=raw_json)

    return demo


demo = build_demo()


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
