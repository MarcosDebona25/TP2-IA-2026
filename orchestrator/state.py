from typing import TypedDict, Optional, Annotated
from pydantic import BaseModel
from datetime import date
import operator


# -------------------------------------------------------------------
# Modelos de datos
# -------------------------------------------------------------------

class PatientMetrics(BaseModel):
    """Series temporales de métricas clínicas del paciente."""
    dates: list[date]
    glucose_fasting: list[float]       # glucosa en ayunas (mg/dL)
    hba1c: list[float]                 # HbA1c (%)
    glucose_postprandial: list[float]  # glucosa postprandial (mg/dL)
    weight: list[float]                # peso (kg)


class Alert(BaseModel):
    """Alerta generada por el Agente Monitor."""
    metric: str
    value: float
    severity: str        # "leve" | "moderada" | "severa"
    date: date           # fecha del registro donde se detectó el valor
    description: str


class MonitorAnalysis(BaseModel):
    """Output estructurado del Agente Monitor."""
    glucose_fasting_stats: dict      # media, std, min, max, tendencia
    hba1c_stats: dict
    glucose_postprandial_stats: dict
    weight_stats: dict
    alerts: list[Alert]
    medication: list[str]
    requires_rag: bool               # flag para el Agente Clínico


# -------------------------------------------------------------------
# Estado del grafo
# -------------------------------------------------------------------

class AgentState(TypedDict):

    # -- Identificación del paciente --
    patient_id: str

    # -- Datos cargados por el Monitor --
    metrics_history: Optional[PatientMetrics]
    medication: Optional[list[str]]

    # -- Output del Agente Monitor --
    analysis: Optional[MonitorAnalysis]

    # -- Contexto RAG recuperado por el Agente Clínico --
    rag_context: Optional[list[str]]

    # -- Reporte generado por el Agente Clínico --
    report: Optional[str]

    # -- Control del grafo --
    iteration: int
    is_followup: bool

    # -- Conversación médico ↔ sistema --
    conversation: Annotated[list[dict], operator.add]