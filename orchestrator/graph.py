# orchestrator/graph.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from orchestrator.state import AgentState
from orchestrator.router import is_followup_message, is_confirmation_message


# -------------------------------------------------------------------
# Stubs de nodos — reemplazar con implementación real progresivamente
# -------------------------------------------------------------------

def orchestrator_node(state: AgentState) -> AgentState:
    """
    Punto de entrada del grafo. Infiere la intención del médico a partir del
    mensaje (state["query"]) y del estado de la sesión, e inicializa el control
    del flujo para esta invocación.

    TODO: reemplazar la heurística de router.py por clasificación vía LLM.
    """
    query = state.get("query") or ""
    return {
        # Routing inferido (heurística por ahora; ver router.py)
        "is_followup": is_followup_message(state, query),
        "awaiting_confirmation": is_confirmation_message(query),
        # Control del loop: se reinicia en cada mensaje nuevo del médico
        "iteration": 0,
        "information_sufficient": True,
    }


def monitor_node(state: AgentState) -> AgentState:
    """
    Analiza las métricas del paciente con tools determinísticas.
    TODO: reemplazar con Agente Monitor real (load_patient_data, calculate_stats,
    detect_threshold_violations, get_medication_schedule).
    """
    # Stub: devuelve análisis vacío
    return {
        "analysis": None,
        "conversation": [{
            "role": "assistant",
            "content": "[Monitor stub] Análisis pendiente de implementación."
        }]
    }


def clinical_node(state: AgentState) -> AgentState:
    """
    Interpreta los hallazgos del Monitor y genera el reporte clínico
    (modos reporte y seguimiento). Antes de redactar, evalúa si la información
    del Monitor alcanza y expone la señal `information_sufficient`.

    TODO: reemplazar con Agente Clínico real (get_patient_history,
    compare_with_previous_sessions, search_clinical_guidelines).
    """
    # Stub: marca la información como suficiente para terminar el flujo end-to-end.
    # El Agente real seteará information_sufficient=False cuando falten datos,
    # disparando el loop de refinamiento (ver decide_next).
    return {
        "report": "[Clinical stub] Reporte pendiente de implementación.",
        "iteration": state.get("iteration", 0) + 1,
        "information_sufficient": True,
        "conversation": [{
            "role": "assistant",
            "content": "[Clínico stub] Reporte pendiente de implementación."
        }]
    }


# -------------------------------------------------------------------
# Funciones de routing — deciden las transiciones condicionales
# -------------------------------------------------------------------

def route_from_orchestrator(state: AgentState) -> str:
    """
    Decide el camino desde el Orquestador:
    - confirmación de guardado  → terminar (la persistencia se conecta luego)
    - pregunta de seguimiento   → directo al Clínico
    - consulta nueva            → pipeline completo (Monitor → Clínico)
    """
    if state.get("awaiting_confirmation"):
        return "save"
    if state.get("is_followup"):
        return "followup"
    return "pipeline"


def decide_next(state: AgentState) -> str:
    """
    Evalúa el estado tras el Agente Clínico y decide si refinar o terminar.
    Implementa el loop de refinamiento descripto en la definición conceptual:
    el Orquestador devuelve el control al Monitor cuando el Clínico señala que
    la información es insuficiente, respetando el guardrail de 3 iteraciones.
    """
    # Guardrail: máximo 3 iteraciones
    if state.get("iteration", 0) >= 3:
        return "end"

    # En seguimiento el Clínico responde directo: no hay refinamiento
    if state.get("is_followup"):
        return "end"

    # Loop de refinamiento: el Clínico marcó información insuficiente
    if not state.get("information_sufficient", True):
        return "monitor"

    return "end"


# -------------------------------------------------------------------
# Construcción del grafo
# -------------------------------------------------------------------

def build_graph():
    graph = StateGraph(AgentState)

    # Registrar nodos
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("monitor", monitor_node)
    graph.add_node("clinical", clinical_node)

    # Entry point
    graph.set_entry_point("orchestrator")

    # El Orquestador decide el flujo según la intención inferida
    graph.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "pipeline": "monitor",
            "followup": "clinical",
            "save": END,
        }
    )

    # El Monitor siempre entrega sus hallazgos al Clínico
    graph.add_edge("monitor", "clinical")

    # El Clínico evalúa si refinar (volver al Monitor) o terminar (guardrail acá)
    graph.add_conditional_edges(
        "clinical",
        decide_next,
        {
            "monitor": "monitor",
            "end": END,
        }
    )

    # Compilar con memoria de sesión (checkpointer por thread_id)
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Instancia global del grafo
app = build_graph()
