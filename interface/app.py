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
    log_view_html,
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

# Tope de filas que se renderizan en el visor de logs. 50 trazas recientes alcanzan para
# el diagnóstico y mantienen la pestaña ágil aunque el .jsonl haya acumulado miles.
_LOG_VIEW_LIMIT = 50


def refresh_logs(event_filter: str) -> str:
    """Recarga las trazas del log y las devuelve como HTML para el visor."""
    entries = load_log_entries(
        None if event_filter == "todos" else event_filter,
        limit=_LOG_VIEW_LIMIT,
    )
    return log_view_html(entries)


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

# Estilos del visor de logs (clase tp2-logs que emite components.log_view_html). Van por el
# parámetro css= de Blocks —no inline en el HTML dinámico— para no reenviarlos en cada refresco
# y para que el navegador los aplique de forma garantizada. Usan variables del tema de Gradio
# (--border-color-primary, etc.) para respetar claro/oscuro.
_LOG_CSS = """
.tp2-logs { font-family: var(--font-mono); font-size: 12px; max-height: 460px;
  overflow-y: auto; border: 1px solid var(--border-color-primary); border-radius: 6px; }
.tp2-head, .tp2-cells { display: grid; gap: 8px; align-items: center;
  grid-template-columns: 96px 84px 150px 1fr; padding: 5px 10px; }
.tp2-head { position: sticky; top: 0; z-index: 1; font-weight: 600;
  background: var(--background-fill-secondary);
  border-bottom: 1px solid var(--border-color-primary); }
.tp2-row { border-bottom: 1px solid var(--border-color-primary); }
.tp2-row > summary { cursor: pointer; list-style: none; }
.tp2-row > summary::-webkit-details-marker { display: none; }
.tp2-row > summary:hover { background: var(--background-fill-secondary); }
.tp2-ts::before { content: "▸ "; color: var(--body-text-color-subdued); }
.tp2-row[open] > summary .tp2-ts::before { content: "▾ "; }
.tp2-nm, .tp2-sm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tp2-ev { color: var(--body-text-color-subdued); }
.tp2-raw { margin: 0; padding: 8px 12px; white-space: pre-wrap; word-break: break-word;
  font-size: 11px; background: var(--background-fill-secondary); }
.tp2-empty { padding: 14px; color: var(--body-text-color-subdued); }
"""


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Monitor Clínico — Diabetes") as demo:
        gr.Markdown(
            "# 🩺 Monitor Clínico — Diabetes tipo 2\n"
            "Sistema multi-agente de soporte a la decisión clínica. "
            "_No emite diagnósticos; es un insumo para el médico tratante._"
        )

        thread_state = gr.State("")

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
            with gr.Tab("Observabilidad (dev)") as obs_tab:
                langsmith_md = gr.Markdown(_langsmith_md())
                with gr.Row():
                    event_filter_dd = gr.Dropdown(
                        choices=["todos", "node", "routing", "llm", "tool"],
                        value="todos", label="Filtrar por tipo de evento", scale=3,
                    )
                    refresh_btn = gr.Button("🔄 Refrescar", scale=1)
                gr.Markdown(
                    "_Trazas (`logs/agent.jsonl`) — hacé clic en una fila para ver su JSON crudo:_"
                )
                # Visor liviano: HTML estático con filas expandibles (components.log_view_html).
                # Reemplaza al gr.Dataframe, cuyo montaje en el navegador congelaba la pestaña
                # ~15 s la primera vez que se abría. El HTML se pinta en milisegundos.
                logs_html = gr.HTML(log_view_html([]))

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

        # Observabilidad: cargar las trazas al ENTRAR a la pestaña (no en el arranque de la
        # app, para no leer el log si el médico nunca abre la vista dev), más refresco manual
        # y al cambiar el filtro. El detalle crudo de cada traza se ve expandiendo su fila.
        for trigger in (refresh_btn.click, event_filter_dd.change, obs_tab.select):
            trigger(refresh_logs, inputs=event_filter_dd, outputs=logs_html)

    return demo


demo = build_demo()


if __name__ == "__main__":
    # En Gradio 6 css y theme se pasan a launch() (ya no al constructor de Blocks).
    demo.launch(theme=gr.themes.Soft(), css=_LOG_CSS)
