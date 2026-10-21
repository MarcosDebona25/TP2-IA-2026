# interface/app.py
#
# Interfaz Gradio del sistema multi-agente (tarea del Integrante D).
#
# Tres pestañas:
#   1. "Consulta" — flujo del médico: ficha del paciente + contexto + acción (barra lateral) y un
#      área principal con indicadores, el reporte junto al chat de seguimiento, y debajo alertas
#      agrupadas y tendencias a todo el ancho.
#   2. "Observabilidad" — visor del log estructurado (logs/agent.jsonl) para desarrollo,
#      con filtro por tipo de evento, refresco y JSON crudo de cada traza.
#   3. "Evaluación" — comparación esperado vs. obtenido de los casos de tests/eval_runner.py.
#
# Conecta al grafo REAL (orchestrator.graph.app): con GROQ_API_KEY usa los agentes ReAct;
# sin ella, el grafo cae a sus fallbacks determinísticos. Los componentes de presentación
# viven en interface/components.py (funciones puras, testeables) y el sistema visual (tema,
# CSS, tipografía, modo claro/oscuro) en interface/theme.py (ADR-0021).

from dotenv import load_dotenv
load_dotenv()

import gradio as gr

from agents.llm_factory import active_model, has_api_key, llm_status
from orchestrator.graph import app as langgraph_app
from interface.logging_config import setup_logging, get_callbacks, tracing_status
from interface.components import (
    alerts_meta,
    alerts_table,
    execution_warning,
    eval_case_choices,
    eval_case_view,
    eval_history_summary_md,
    eval_run_choices,
    eval_summary_md,
    find_eval_case,
    format_report,
    get_eval_run,
    list_patients,
    load_eval_history,
    load_log_entries,
    log_view_html,
    patient_profile,
    summary_strip,
    trends_view,
)
from interface.theme import CSS, HEAD, LOGO_PATH, THEME, THEME_TOGGLE_JS, appbar_html, card_head
from tools.history_tools import get_patient_history
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


def _status_pill() -> tuple[str, bool, str]:
    """(texto corto, hay LLM, detalle completo) del modo de ejecución, para la barra superior."""
    if not has_api_key():
        return "Modo determinístico · sin LLM", False, llm_status()
    _, model = active_model()
    return f"LLM · {model.split('/')[-1]}", True, llm_status()


def _alerts_head(alerts=None) -> str:
    return card_head("Alertas", alerts_meta(alerts or []))


# -------------------------------------------------------------------
# Callbacks de la UI — pestaña "Consulta"
# -------------------------------------------------------------------

def on_patient_change(patient_id: str) -> str:
    """Carga la ficha del paciente al seleccionarlo (paso 2 del flujo)."""
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
    history = get_patient_history(patient_id) if patient_id else None
    return patient_profile(patient_id, metrics, meds, history)


def analyze(patient_id: str, doctor_context: str):
    """
    Lanza el análisis completo (Monitor → Clínico) sobre un paciente nuevo.

    Devuelve (chat, thread_id, reporte, alertas, tendencias, indicadores, encabezado de alertas).
    """
    if not patient_id:
        aviso = "Elegí un paciente antes de analizar."
        return ([{"role": "assistant", "content": aviso}], "", format_report(None), alerts_table(None),
                trends_view(None), summary_strip(None), _alerts_head())

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
        err = f"Error al ejecutar el análisis: {e}"
        return ([{"role": "assistant", "content": err}], thread_id, format_report(None), alerts_table(None),
                trends_view(None), summary_strip(None), _alerts_head())

    # Paciente sin datos en el EHR: se informa y no se muestran alertas ni tendencias (ADR-0003)
    error = out.get("error")
    if error:
        sin_datos = "<p class='tp2-muted'>Sin análisis: no hay datos del paciente en el EHR.</p>"
        reporte = f"### {error}\n\nNo se generó reporte: el sistema no analiza pacientes sin datos."
        return ([{"role": "assistant", "content": error}], thread_id, format_report(reporte), sin_datos,
                sin_datos, summary_strip(None), _alerts_head())

    analysis = out.get("analysis")
    alerts = analysis.alerts if analysis else []
    aviso = execution_warning(out.get("execution_mode"))
    chat = [{
        "role": "assistant",
        "content": (
            f"Análisis de **{patient_id}** listo: {len(alerts)} alerta(s). "
            "El reporte está en el panel central; podés hacer preguntas de seguimiento acá."
            + (f"\n\n{aviso}" if aviso else "")
        ),
    }]
    reporte = format_report(out.get("report"))
    if aviso:
        reporte = f"> {aviso}\n\n{reporte}"
    return (chat, thread_id, reporte, alerts_table(alerts), trends_view(analysis),
            summary_strip(analysis), _alerts_head(alerts))


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
        before = langgraph_app.get_state(_config(thread_id)).values.get("active_patient_id")
        out = langgraph_app.invoke({"query": message}, _config(thread_id))
        reply = _last_assistant(out.get("conversation", []))
        aviso = execution_warning(out.get("execution_mode"))
        if aviso:
            reply += f"\n\n{aviso}"
        after = out.get("active_patient_id")
        if before and after and after != before:
            # El grafo cambió de paciente (ADR-0004), pero los paneles no se actualizan desde el chat.
            reply += (
                f"\n\n**El análisis cambió de {before} a {after}.** El reporte, las alertas y las "
                f"tendencias siguen mostrando a {before}: elegí {after} y usá **Analizar paciente**."
            )
    except Exception as e:
        reply = f"Error: {e}"

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
        # Señal explícita (D5): no depende de interpretar texto.
        out = langgraph_app.invoke({"save_requested": True, "query": "guardar sesión"}, _config(thread_id))
        msg = _last_assistant(out.get("conversation", []))
    except Exception as e:
        msg = f"Error al guardar: {e}"
    return history + [
        {"role": "user", "content": "Guardar sesión"},
        {"role": "assistant", "content": msg},
    ]


def reset_session():
    """Limpia la sesión para empezar una consulta nueva."""
    return ([], "", format_report(None), alerts_table(None), trends_view(None), summary_strip(None),
            _alerts_head(), "")


# -------------------------------------------------------------------
# Callbacks de la UI — pestaña "Observabilidad"
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


def _langsmith_html() -> str:
    st = tracing_status()
    activo = st["langsmith_enabled"] and st["has_api_key"]
    pill = ("<span class='tp2-pill is-ok'>LangSmith activo</span>" if activo else
            "<span class='tp2-pill is-neutral'>LangSmith inactivo</span>")
    proj = st.get("project") or "—"
    return (
        f"<div class='tp2-card-head'><div style='display:flex;gap:10px;align-items:center'>{pill}"
        f"<span class='tp2-card-meta'>proyecto <code>{proj}</code> · "
        "<a href='https://smith.langchain.com' target='_blank' rel='noopener'>abrir dashboard</a></span></div>"
        "<span class='tp2-card-meta'>Trazas locales en <code>logs/agent.jsonl</code> · "
        "clic en una fila para ver el JSON</span></div>"
    )


# -------------------------------------------------------------------
# Callbacks de la UI — pestaña "Evaluación"
# -------------------------------------------------------------------

def _eval_case_panels(run, case_id=None):
    """(case_dd update, contexto, esperado, obtenido) para una corrida y caso dados."""
    case_choices = eval_case_choices(run)
    first = find_eval_case(run, case_id)
    case_id = first.get("id") if first else None
    context, expected, obtained = eval_case_view(run, case_id)
    return gr.update(choices=case_choices, value=case_id), context, expected, obtained


def load_eval():
    """
    Lee el historial de logs/eval_report.json y prepara la pestaña: resumen del historial,
    selector de corrida (última seleccionada), selector de caso y la comparación del primer
    caso de esa corrida. Se dispara al entrar a la pestaña y al refrescar.
    """
    history = load_eval_history()
    run_choices = eval_run_choices(history)
    latest_idx = (len(history) - 1) if history else None
    run = get_eval_run(history, latest_idx)
    case_dd_upd, context, expected, obtained = _eval_case_panels(run)
    return (
        history,                                          # eval_state
        eval_history_summary_md(history),                 # eval_history_summary
        gr.update(choices=run_choices, value=latest_idx), # eval_run_dd
        eval_summary_md(run),                             # eval_summary (de la corrida)
        case_dd_upd,                                      # eval_case_dd
        context, expected, obtained,                      # paneles
    )


def select_run(history, run_idx):
    """Al elegir otra corrida: re-renderiza su resumen, su selector de casos y el primer caso."""
    run = get_eval_run(history, run_idx)
    case_dd_upd, context, expected, obtained = _eval_case_panels(run)
    return eval_summary_md(run), case_dd_upd, context, expected, obtained


def show_eval_case(history, run_idx, case_id):
    """Re-renderiza la comparación al elegir otro caso dentro de la corrida actual."""
    run = get_eval_run(history, run_idx)
    return eval_case_view(run, case_id)


# -------------------------------------------------------------------
# Construcción de la UI
# -------------------------------------------------------------------

def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Monitor Clínico · Diabetes tipo 2") as demo:
        # Barra superior: marca, modo de ejecución del LLM (ADR-0018) y selector de tema.
        gr.HTML(
            appbar_html(*_status_pill()),
            js_on_load=THEME_TOGGLE_JS,
            elem_classes="tp2-appbar-wrap",
        )

        thread_state = gr.State("")

        with gr.Tabs(elem_classes="tp2-tabs"):
            # ---------------- Pestaña 1: Consulta ----------------
            with gr.Tab("Consulta"):
                with gr.Row(equal_height=False):
                    # Columna izquierda: paciente + contexto + acción
                    with gr.Column(scale=3, min_width=280, elem_classes="tp2-sidebar"):
                        with gr.Column(elem_classes="tp2-card"):
                            gr.HTML("<p class='tp2-eyebrow'>Paciente</p>")
                            patient_dd = gr.Dropdown(
                                choices=list_patients(), value=None, show_label=False,
                                container=False, info=None,
                            )
                            profile_html = gr.HTML(patient_profile("", None, None))
                        with gr.Column(elem_classes="tp2-card"):
                            gr.HTML("<p class='tp2-eyebrow'>Contexto clínico</p>")
                            context_tb = gr.Textbox(
                                show_label=False, container=False, lines=4,
                                placeholder="Opcional: síntomas recientes, eventos intercurrentes, "
                                            "adherencia referida…",
                            )
                            analyze_btn = gr.Button(
                                "Analizar paciente", variant="primary", size="lg",
                                elem_classes="tp2-primary-btn",
                            )

                    # Área principal: indicadores → reporte + chat → alertas y tendencias a lo ancho
                    with gr.Column(scale=10, min_width=520):
                        summary_html = gr.HTML(summary_strip(None))
                        with gr.Row(equal_height=False):
                            with gr.Column(scale=7, min_width=420):
                                with gr.Column(elem_classes="tp2-card"):
                                    gr.HTML(card_head("Reporte clínico", "Agente Clínico · guías + historial"))
                                    report_md = gr.Markdown(format_report(None))
                            # Chat de seguimiento, fijo al hacer scroll por el reporte
                            with gr.Column(scale=5, min_width=320, elem_classes="tp2-chat-col"):
                                with gr.Column(elem_classes="tp2-card"):
                                    gr.HTML(card_head("Seguimiento", "Preguntas sobre el reporte"))
                                    chatbot = gr.Chatbot(
                                        show_label=False, height=420, buttons=["copy_all"],
                                        placeholder="Analizá un paciente para habilitar el seguimiento.",
                                    )
                                    query_tb = gr.Textbox(
                                        show_label=False, submit_btn=True, container=False,
                                        placeholder="Escribí una pregunta…",
                                    )
                                    with gr.Row(elem_classes="tp2-chat-actions"):
                                        save_btn = gr.Button("Guardar sesión", variant="secondary", size="md")
                                        reset_btn = gr.Button("Nueva consulta", variant="secondary", size="md")
                        with gr.Column(elem_classes="tp2-card"):
                            alerts_head = gr.HTML(_alerts_head())
                            alerts_html = gr.HTML(alerts_table(None))
                        with gr.Column(elem_classes="tp2-card"):
                            gr.HTML(card_head("Tendencias", "Agente Monitor · ventana analizada"))
                            trends_html = gr.HTML(trends_view(None))

            # ---------------- Pestaña 2: Observabilidad ----------------
            with gr.Tab("Observabilidad") as obs_tab:
                with gr.Column(elem_classes="tp2-card"):
                    gr.HTML(_langsmith_html())
                    with gr.Row():
                        event_filter_dd = gr.Dropdown(
                            choices=["todos", "node", "routing", "llm", "tool"],
                            value="todos", label="Tipo de evento", scale=4,
                        )
                        refresh_btn = gr.Button("Refrescar", variant="secondary", scale=1)
                    # Visor liviano: HTML estático con filas expandibles (components.log_view_html).
                    # Reemplaza al gr.Dataframe, cuyo montaje en el navegador congelaba la pestaña
                    # ~15 s la primera vez que se abría. El HTML se pinta en milisegundos.
                    logs_html = gr.HTML(log_view_html([]))

            # ---------------- Pestaña 3: Evaluación ----------------
            # Lee el artefacto logs/eval_report.json (lo produce tests/eval_runner.py) y muestra
            # una comparación clara esperado vs. obtenido por caso, para puntuar la calidad a ojo.
            with gr.Tab("Evaluación") as eval_tab:
                eval_state = gr.State([])  # historial de corridas cargado (lista)
                with gr.Column(elem_classes="tp2-card"):
                    with gr.Row():
                        eval_history_summary = gr.Markdown(eval_history_summary_md(None))
                        eval_refresh_btn = gr.Button("Refrescar", variant="secondary", scale=0, min_width=120)
                    with gr.Row():
                        eval_run_dd = gr.Dropdown(
                            choices=[], label="Corrida", scale=2,
                            info="Cada ejecución de eval_runner.py agrega una corrida al historial.",
                        )
                        eval_case_dd = gr.Dropdown(
                            choices=[], label="Caso de evaluación", scale=3,
                            info="Casos evaluados en la corrida seleccionada.",
                        )
                    eval_summary = gr.Markdown(eval_summary_md(None))
                with gr.Column(elem_classes="tp2-card"):
                    eval_context_md = gr.Markdown("_Elegí un caso para ver la comparación._")
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        with gr.Column(elem_classes="tp2-card tp2-eval-panel"):
                            gr.HTML(card_head("Comportamiento esperado"))
                            eval_expected_md = gr.Markdown("", elem_classes="tp2-eval-expected")
                    with gr.Column(scale=1):
                        with gr.Column(elem_classes="tp2-card tp2-eval-panel"):
                            gr.HTML(card_head("Salida obtenida"))
                            eval_obtained_md = gr.Markdown("", elem_classes="tp2-eval-obtained")

        # ---------------- Wiring de eventos ----------------
        patient_dd.change(on_patient_change, inputs=patient_dd, outputs=profile_html)

        analysis_outputs = [chatbot, thread_state, report_md, alerts_html, trends_html,
                            summary_html, alerts_head]
        analyze_btn.click(analyze, inputs=[patient_dd, context_tb], outputs=analysis_outputs)

        query_tb.submit(
            follow_up,
            inputs=[query_tb, chatbot, thread_state],
            outputs=[chatbot, query_tb],
        )

        save_btn.click(save_session, inputs=[thread_state, chatbot], outputs=chatbot)

        reset_btn.click(reset_session, outputs=analysis_outputs + [context_tb])

        # Observabilidad: cargar las trazas al ENTRAR a la pestaña (no en el arranque de la
        # app, para no leer el log si el médico nunca abre la vista dev), más refresco manual
        # y al cambiar el filtro. El detalle crudo de cada traza se ve expandiendo su fila.
        for trigger in (refresh_btn.click, event_filter_dd.change, obs_tab.select):
            trigger(refresh_logs, inputs=event_filter_dd, outputs=logs_html)

        # Evaluación: al ENTRAR a la pestaña y al refrescar, cargar el historial (resumen +
        # selector de corrida + selector de caso + comparación del primer caso de la última
        # corrida). Al cambiar de corrida se re-arma su resumen/casos; al cambiar de caso, solo
        # la comparación.
        eval_load_outputs = [
            eval_state, eval_history_summary, eval_run_dd, eval_summary, eval_case_dd,
            eval_context_md, eval_expected_md, eval_obtained_md,
        ]
        for trigger in (eval_refresh_btn.click, eval_tab.select):
            trigger(load_eval, outputs=eval_load_outputs)

        eval_run_dd.change(
            select_run,
            inputs=[eval_state, eval_run_dd],
            outputs=[eval_summary, eval_case_dd,
                     eval_context_md, eval_expected_md, eval_obtained_md],
        )

        eval_case_dd.change(
            show_eval_case,
            inputs=[eval_state, eval_run_dd, eval_case_dd],
            outputs=[eval_context_md, eval_expected_md, eval_obtained_md],
        )

    return demo


demo = build_demo()


def launch(**kwargs) -> None:
    """Lanza la UI. En Gradio 6 css y theme se pasan a launch() (ya no al constructor de Blocks)."""
    kwargs.setdefault("favicon_path", str(LOGO_PATH))
    demo.launch(theme=THEME, css=CSS, head=HEAD, **kwargs)


if __name__ == "__main__":
    launch()
