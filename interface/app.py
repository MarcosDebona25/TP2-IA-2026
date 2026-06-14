from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from orchestrator.graph import app as langgraph_app
from interface.logging_config import setup_logging, get_callbacks

# Configura el logging propio (consola legible + logs/agent.jsonl) al iniciar.
setup_logging()

_thread_counter = 0


def _next_thread_id() -> str:
    global _thread_counter
    _thread_counter += 1
    return f"session-{_thread_counter}"


def chat(message: str, history: list, patient_id: str, thread_id: str, report: str):
    if not patient_id.strip():
        history = history + [{"role": "user", "content": message}, {"role": "assistant", "content": "Por favor ingresá un ID de paciente antes de consultar."}]
        return history, thread_id, report

    state_input = {"query": message, "conversation": []}
    if not thread_id:
        thread_id = _next_thread_id()
        state_input["patient_id"] = patient_id.strip()

    config = {"configurable": {"thread_id": thread_id}, "callbacks": get_callbacks()}
    out = langgraph_app.invoke(state_input, config)

    new_report = out.get("report") or report
    agent_reply = out.get("conversation", [{}])[-1].get("content", "(sin respuesta)")

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": agent_reply},
    ]
    return history, thread_id, new_report


def reset_session():
    return [], "", "", ""


with gr.Blocks(title="Monitor Clínico — Diabetes") as demo:
    gr.Markdown("# Monitor Clínico — Diabetes\nSistema multi-agente de análisis de pacientes diabéticos.")

    thread_state = gr.State("")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="Conversación",
                height=500,
                buttons=["copy", "copy_all"],
                placeholder="Iniciá una consulta sobre un paciente...",
            )
            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="Escribí tu consulta...",
                    show_label=False,
                    scale=4,
                    submit_btn=True,
                )

        with gr.Column(scale=1):
            patient_input = gr.Textbox(label="ID del Paciente", placeholder="ej. P001")
            report_output = gr.Textbox(
                label="Reporte Clínico",
                lines=12,
                interactive=False,
                placeholder="El reporte aparecerá aquí tras el análisis...",
            )
            reset_btn = gr.Button("Nueva sesión", variant="secondary")

    msg_input.submit(
        fn=chat,
        inputs=[msg_input, chatbot, patient_input, thread_state, report_output],
        outputs=[chatbot, thread_state, report_output],
    ).then(lambda: "", outputs=msg_input)

    reset_btn.click(
        fn=reset_session,
        outputs=[chatbot, thread_state, patient_input, report_output],
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
