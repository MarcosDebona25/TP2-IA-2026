# orchestrator/router.py
#
# Lógica de routing del Orquestador, separada del grafo para poder testearla
# de forma aislada y reemplazarla luego por una clasificación vía LLM.

from orchestrator.state import AgentState

# Palabras clave de confirmación / cancelación del guardado de sesión
_CONFIRM_WORDS = {"confirmar", "confirm", "sí", "si", "yes"}
_CANCEL_WORDS = {"cancelar", "cancel", "no"}


def is_followup_message(state: AgentState, message: str) -> bool:
    """
    Determina si el mensaje del médico es un follow-up sobre el reporte ya
    generado o una consulta nueva que requiere el pipeline completo.

    Criterio simple: si hay reporte en el estado y el mensaje no menciona
    explícitamente un paciente distinto → es follow-up.

    TODO: reemplazar con clasificación vía LLM del Orquestador.
    """
    if not state.get("report"):
        return False

    # Si el mensaje habla de un paciente cuyo id no coincide con el activo
    # → es una consulta nueva, no un seguimiento.
    patient_id = state.get("patient_id")
    if "paciente" in message.lower() and patient_id and patient_id not in message:
        return False

    return True


def is_confirmation_message(message: str) -> bool:
    """Detecta si el médico confirmó guardar la sesión."""
    return message.strip().lower() in _CONFIRM_WORDS


def is_cancellation_message(message: str) -> bool:
    """Detecta si el médico canceló el guardado de la sesión."""
    return message.strip().lower() in _CANCEL_WORDS
