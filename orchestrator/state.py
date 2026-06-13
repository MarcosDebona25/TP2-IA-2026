from typing import TypedDict, Optional, Annotated
from pydantic import BaseModel
from datetime import date
import operator


# -------------------------------------------------------------------
# Modelos de datos — métricas del paciente
# -------------------------------------------------------------------

class CGMMetrics(BaseModel):   #SE DEFINE PERO NO SE USA, QUEDA FUERA DEL ALCANCE DEL TP
    """Métricas derivadas de monitoreo continuo de glucosa (CGM)."""
    time_in_range: float           # TIR: % lecturas entre 70-180 mg/dL
    time_below_range: float        # TBR: % lecturas < 70 mg/dL
    time_above_range: float        # TAR: % lecturas > 180 mg/dL
    coefficient_of_variation: float  # CV >= 36% indica alta variabilidad
    nocturnal_hypo_episodes: int   # episodios de hipoglucemia nocturna
    glucose_mean: float            # glucosa media del período
    estimated_hba1c: float         # HbA1c estimada a partir del CGM


class PatientMetrics(BaseModel):
    """Series temporales de métricas clínicas del paciente (EHR)."""
    dates: list[date]
    glucose_fasting: list[float]        # glucosa en ayunas (mg/dL)
    hba1c: list[float]                  # HbA1c (%)
    glucose_postprandial: list[float]   # glucosa postprandial (mg/dL)
    weight: list[float]                 # peso (kg)
    blood_pressure_systolic: list[float]   # presión sistólica (mmHg)
    blood_pressure_diastolic: list[float]  # presión diastólica (mmHg)
    cgm_series: Optional[list[float]] = None  # lecturas CGM crudas (cada 5-15 min)


# -------------------------------------------------------------------
# Modelos de datos — medicación y estadísticas
# -------------------------------------------------------------------

class Medication(BaseModel):
    """Medicación activa del paciente (output de get_medication_schedule)."""
    name: str            # nombre del fármaco
    dose: str            # dosis (p. ej. "850mg")
    frequency: str       # frecuencia (p. ej. "cada 12h")


class MetricStats(BaseModel):
    """Estadísticas calculadas para una métrica (output de calculate_stats)."""
    mean: float          # media
    std: float           # desviación estándar
    trend: float         # pendiente de la tendencia lineal
    last_value: float    # último valor registrado


class BloodPressureStats(BaseModel):
    """Estadísticas de presión arterial (dos series: sistólica y diastólica)."""
    systolic: MetricStats
    diastolic: MetricStats


# -------------------------------------------------------------------
# Modelos de datos — análisis y alertas
# -------------------------------------------------------------------

class Alert(BaseModel):
    """Alerta generada por el Agente Monitor."""
    metric: str
    value: float
    severity: str        # "leve" | "moderada" | "severa"
    date: date           # fecha del registro donde se detectó el valor
    description: str


class MonitorAnalysis(BaseModel):
    """Output estructurado del Agente Monitor."""
    glucose_fasting_stats: MetricStats
    hba1c_stats: MetricStats
    glucose_postprandial_stats: MetricStats
    weight_stats: MetricStats
    blood_pressure_stats: BloodPressureStats
    cgm_metrics: Optional[CGMMetrics] = None  # None si el paciente no tiene CGM
    alerts: list[Alert]
    medication: list[Medication]
    requires_rag: bool                    # hay alertas moderadas o severas
    requires_longitudinal_comparison: bool  # hay métricas que ameritan comparar con sesiones anteriores


# -------------------------------------------------------------------
# Estado del grafo
# -------------------------------------------------------------------

class AgentState(TypedDict):

    # -- Identificación del paciente --
    patient_id: str

    # -- Mensaje actual del médico --
    query: str            # consulta/pregunta actual (consumida por los templates)

    # -- Datos cargados desde EHR --
    metrics_history: Optional[PatientMetrics]
    medication: Optional[list[Medication]]

    # -- Historial acumulativo desde MongoDB --
    patient_history: Optional[dict]   # documento completo del paciente

    # -- Output del Agente Monitor --
    analysis: Optional[MonitorAnalysis]

    # -- Comparación longitudinal (Agente Clínico) --
    longitudinal_comparison: Optional[dict]

    # -- Contexto RAG recuperado por el Agente Clínico --
    rag_context: Optional[list[str]]

    # -- Reporte generado por el Agente Clínico --
    # has_report se deriva de (report is not None) al formatear el template del Orquestador
    report: Optional[str]

    # -- Control del grafo --
    iteration: int        # contador para el guardrail (máx 3)
    is_followup: bool     # True si es pregunta de seguimiento, False si es consulta nueva
    awaiting_confirmation: bool  # True si se espera confirmación del médico para guardar sesión
    information_sufficient: bool  # señal del Clínico: False → el Orquestador reenvía al Monitor (loop de refinamiento)

    # -- Conversación médico ↔ sistema --
    conversation: Annotated[list[dict], operator.add]

    # -- Contexto clínico adicional ingresado por el médico --
    doctor_context: Optional[str]   # orientación o contexto libre del médico