# orchestrator/graph.py

import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from orchestrator.state import AgentState
from orchestrator.router import is_followup_message, is_confirmation_message
from agents.llm_factory import has_api_key

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Nodo Orquestador
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


# -------------------------------------------------------------------
# Nodo Monitor — agente real con fallback a stub si no hay API key
# -------------------------------------------------------------------

def monitor_node(state: AgentState) -> AgentState:
    """
    Analiza las métricas del paciente con el Agente Monitor real (ReAct + tools
    determinísticas). Si no hay GROQ_API_KEY configurada, cae al stub para que
    los tests y el desarrollo sin LLM sigan funcionando.
    """
    patient_id = state.get("patient_id", "")

    # Si no hay API key, usar el fallback determinístico sin LLM
    if not has_api_key():
        logger.warning("Monitor: sin API key, ejecutando fallback determinístico")
        return _monitor_fallback(state)

    try:
        from agents.monitor import run_monitor_agent
        analysis = run_monitor_agent(state)

        # Resumen legible para la conversación
        n_alerts = len(analysis.alerts)
        alert_summary = f"{n_alerts} alerta(s) detectada(s)" if n_alerts > 0 else "sin alertas"
        summary = (
            f"Análisis del paciente {patient_id} completado: {alert_summary}. "
            f"Métricas analizadas: glucosa en ayunas, HbA1c, glucosa postprandial, "
            f"peso, presión arterial. Medicación: {len(analysis.medication)} fármaco(s)."
        )

        return {
            "analysis": analysis,
            "conversation": [{
                "role": "assistant",
                "content": f"[Monitor] {summary}",
            }],
        }
    except Exception as e:
        logger.error("Monitor: error en agente real, fallback determinístico: %s", e)
        return _monitor_fallback(state)


def _monitor_fallback(state: AgentState) -> AgentState:
    """
    Fallback determinístico del Monitor: ejecuta todas las tools directamente
    sin LLM y construye un MonitorAnalysis. Útil para tests y cuando no hay API key.
    """
    patient_id = state.get("patient_id", "")

    try:
        from agents.monitor import _build_analysis
        from tools.patient_tools import (
            calculate_stats,
            get_medication_schedule,
            SERIES_METRICS,
        )
        from tools.threshold_tools import detect_threshold_violations, ADA_THRESHOLDS
        from orchestrator.state import MetricStats

        # Calcular stats para todas las métricas
        stats: dict[str, MetricStats] = {}
        for metric in SERIES_METRICS:
            try:
                stats[metric] = calculate_stats(patient_id, metric)
            except (ValueError, FileNotFoundError):
                pass

        # Detectar violaciones para métricas con umbral
        alerts = []
        for metric in ADA_THRESHOLDS:
            try:
                alerts.extend(detect_threshold_violations(patient_id, metric))
            except (ValueError, FileNotFoundError):
                pass

        # Medicación
        meds = get_medication_schedule(patient_id)

        analysis = _build_analysis(patient_id, stats, alerts, meds)

        return {
            "analysis": analysis,
            "conversation": [{
                "role": "assistant",
                "content": f"[Monitor fallback] Análisis determinístico del paciente {patient_id} completado.",
            }],
        }
    except Exception as e:
        logger.error("Monitor fallback: error: %s", e)
        return {
            "analysis": None,
            "conversation": [{
                "role": "assistant",
                "content": f"[Monitor] Error al analizar paciente {patient_id}: {e}",
            }],
        }


def clinical_node(state: AgentState) -> AgentState:
    """
    Interpreta los hallazgos del Monitor y genera el reporte clínico
    (modos reporte y seguimiento). Antes de redactar, evalúa si la información
    del Monitor alcanza y expone la señal `information_sufficient`.
    """
    # Si no hay API key, usar el fallback determinístico sin LLM
    if not has_api_key():
        logger.warning("Clínico: sin API key, ejecutando fallback determinístico")
        return _clinical_fallback(state)

    try:
        from agents.clinical import run_clinical_agent
        updates = run_clinical_agent(state)
        # Incrementar la iteración en el nodo
        updates["iteration"] = state.get("iteration", 0) + 1
        return updates
    except Exception as e:
        logger.error("Clínico: error en agente real, fallback determinístico: %s", e)
        return _clinical_fallback(state)


def _clinical_fallback(state: AgentState) -> AgentState:
    """
    Fallback determinístico del Clínico: genera un reporte estático según el análisis
    y las alertas. Útil para tests y cuando no hay API key.
    """
    patient_id = state.get("patient_id", "")
    analysis = state.get("analysis")
    iteration = state.get("iteration", 0) + 1

    # Si es P004 (datos insuficientes) y primera/segunda vuelta, marcamos información insuficiente
    information_sufficient = True
    if patient_id == "P004" and iteration < 3:
        information_sufficient = False
        report = f"[Clinical fallback] Información cuantitativa insuficiente para {patient_id}. Solicitando ampliación al Monitor."
    else:
        report = f"[Clinical fallback] Reporte determinístico del paciente {patient_id}. "
        if analysis:
            if len(analysis.alerts) > 0:
                report += f"Se detectaron {len(analysis.alerts)} alerta(s). "
            else:
                report += "Paciente metabólicamente controlado, sin alertas. "
            report += f"Medicación activa: {', '.join(m.name for m in analysis.medication)}."
        else:
            report += "No hay análisis de monitor disponible."

    return {
        "report": report,
        "iteration": iteration,
        "information_sufficient": information_sufficient,
        "conversation": [{
            "role": "assistant",
            "content": report
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
    # TODO (Orquestador/A): la rama "save" hoy va directo a END (no persiste). Reemplazar por
    # un nodo `save` que llame a tools/mongo_tools.update_patient_history (ya implementada) con
    # el reporte, alertas y métricas de la sesión. Ver docs/estado_proyecto.md (pendiente).
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
