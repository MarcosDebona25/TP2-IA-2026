# tools/patient_tools.py
#
# Tools determinísticas del Agente Monitor que operan sobre el EHR (datos del paciente).
# Por ahora leen de `data/sample/` (fixture provisional, contrato #1) hasta que B entregue
# el generador real y MongoDB.
#
# ── Lineamiento de métricas (contrato A+C, ver "Flujo de métricas" en docs/CLAUDE.md) ──
#  - El Agente Monitor es un agente ReAct: el LLM razona QUÉ métricas y QUÉ ventana temporal
#    analizar (no hace aritmética). Las tools son finas y separadas (§2.6), determinísticas.
#  - Las tools se invocan por `patient_id` (+ `metric` + `timerange`): cargan y recortan los
#    datos internamente, de modo que el LLM nunca mueve arrays, solo identificadores chicos.
#  - El recorte temporal se hace en UN solo lugar: `window_metrics()` (helper de ventaneo).
#  - Cada tool delega el cálculo en un núcleo puro (`_compute_stats`) testeable con listas.
#
# Devuelven los modelos Pydantic de orchestrator/state.py (no dicts), según el contrato #3.
# El Agente Monitor (A) las envuelve como tools de LangChain (@tool / StructuredTool).
#
# Tools de MongoDB (get_patient_history, compare_with_previous_sessions,
# update_patient_history): NO van acá — dependen de B. Pendientes.

from __future__ import annotations

import csv
import json
import statistics
from datetime import date
from pathlib import Path
from typing import Optional

from orchestrator.state import Medication, MetricStats, PatientMetrics, TimeRange

# -------------------------------------------------------------------
# Rutas y schema del CSV
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_DIR = PROJECT_ROOT / "data" / "sample"

# Métricas válidas = series numéricas de PatientMetrics (una por columna del CSV).
SERIES_METRICS = (
    "glucose_fasting",
    "hba1c",
    "glucose_postprandial",
    "weight",
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
)


# -------------------------------------------------------------------
# Tool 1 — load_patient_data
# -------------------------------------------------------------------

def load_patient_data(patient_id: str, data_dir: Path | None = None) -> PatientMetrics:
    """
    Carga el historial clínico COMPLETO del paciente desde el EHR (CSV `{patient_id}.csv`).

    Se invoca una vez por consulta (puebla state["metrics_history"]); las tools de análisis
    vuelven a cargarlo por `patient_id` y lo recortan con `window_metrics`. Devuelve un
    `PatientMetrics` con las series ordenadas por fecha ascendente. FileNotFoundError si el
    paciente no existe.

    TO DO (B): reemplazar la lectura de `data/sample/` por la fuente real (generador + Mongo/EHR).
    """
    base = data_dir or SAMPLE_DATA_DIR
    csv_path = base / f"{patient_id}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No hay datos de EHR para el paciente '{patient_id}' en {csv_path}")

    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        raise ValueError(f"El paciente '{patient_id}' no tiene datos cargados")

    # Orden cronológico estable (no asumimos que las filas vengan ordenadas).
    rows.sort(key=lambda r: r["date"])

    return PatientMetrics(
        dates=[date.fromisoformat(r["date"]) for r in rows],
        glucose_fasting=[float(r["glucose_fasting"]) for r in rows],
        hba1c=[float(r["hba1c"]) for r in rows],
        glucose_postprandial=[float(r["glucose_postprandial"]) for r in rows],
        weight=[float(r["weight"]) for r in rows],
        blood_pressure_systolic=[float(r["blood_pressure_systolic"]) for r in rows],
        blood_pressure_diastolic=[float(r["blood_pressure_diastolic"]) for r in rows],
    )


# -------------------------------------------------------------------
# Ventaneo temporal — ÚNICA implementación del recorte por timerange
# -------------------------------------------------------------------

def window_metrics(metrics: PatientMetrics, timerange: Optional[TimeRange] = None) -> PatientMetrics:
    """
    Recorta TODAS las series de `metrics` a la ventana `timerange` y devuelve un nuevo
    `PatientMetrics`. Fuente única del filtrado temporal (la reusan calculate_stats y
    detect_threshold_violations; no se duplica la lógica).

      - timerange None o global        → devuelve la serie completa (sin recortar).
      - timerange.last_n_months = N    → los últimos N registros mensuales.
      - timerange.start / end          → registros con fecha en [start, end] inclusive.
    """
    if timerange is None or timerange.is_global:
        return metrics

    n = len(metrics.dates)
    if timerange.last_n_months is not None:
        indices = list(range(max(0, n - timerange.last_n_months), n))
    else:
        indices = [
            i for i, d in enumerate(metrics.dates)
            if (timerange.start is None or d >= timerange.start)
            and (timerange.end is None or d <= timerange.end)
        ]
    return _subset(metrics, indices)


def _subset(metrics: PatientMetrics, indices: list[int]) -> PatientMetrics:
    """Construye un PatientMetrics con solo las posiciones `indices` de cada serie."""
    pick = lambda seq: [seq[i] for i in indices]
    return PatientMetrics(
        dates=pick(metrics.dates),
        glucose_fasting=pick(metrics.glucose_fasting),
        hba1c=pick(metrics.hba1c),
        glucose_postprandial=pick(metrics.glucose_postprandial),
        weight=pick(metrics.weight),
        blood_pressure_systolic=pick(metrics.blood_pressure_systolic),
        blood_pressure_diastolic=pick(metrics.blood_pressure_diastolic),
        cgm_series=metrics.cgm_series,  # CGM fuera de alcance: se conserva sin recortar.
    )


def get_metric_series(metrics: PatientMetrics, metric: str) -> list[float]:
    """Devuelve la serie numérica de `metric`. ValueError si la métrica no existe."""
    if metric not in SERIES_METRICS:
        raise ValueError(f"Métrica desconocida: '{metric}'. Válidas: {list(SERIES_METRICS)}")
    return getattr(metrics, metric)


# -------------------------------------------------------------------
# Tool 2 — calculate_stats  (wrapper) + núcleo puro
# -------------------------------------------------------------------

def calculate_stats(
    patient_id: str,
    metric: str,
    timerange: Optional[TimeRange] = None,
    data_dir: Path | None = None,
) -> MetricStats:
    """
    Estadísticas de `metric` para `patient_id` sobre la ventana `timerange` (global si None).

    Carga los datos, los recorta con `window_metrics`, extrae la serie de `metric` y delega
    el cálculo en `_compute_stats`. `metric` selecciona la serie (debe ser una de
    SERIES_METRICS). Lanza ValueError si la ventana queda sin registros.
    """
    metrics = window_metrics(load_patient_data(patient_id, data_dir), timerange)
    values = get_metric_series(metrics, metric)
    if not values:
        raise ValueError(f"No hay datos de '{metric}' para '{patient_id}' en la ventana indicada")
    return _compute_stats(values)


# Banda muerta relativa: si |cambio neto| < 3% de la media, la tendencia se considera "estable"
# (evita marcar como subiendo/bajando un ruido clínicamente irrelevante). Escala-independiente.
_STABLE_REL_BAND = 0.03


def _compute_stats(values: list[float]) -> MetricStats:
    """
    Núcleo determinístico de estadísticas clínicamente accionables (ver MetricStats):
    último valor, media, mínimo, máximo, cambio neto (delta) y dirección legible. Testeable
    con listas.

    Requiere ≥ 1 valor. Con un solo registro: min=max=last=mean, delta=0, direction="estable".
    El criterio de "datos insuficientes" (< 2 registros) lo aplica el Agente Monitor.
    """
    if not values:
        raise ValueError("_compute_stats requiere al menos un valor")
    mean = statistics.fmean(values)
    delta = values[-1] - values[0]
    return MetricStats(
        last_value=values[-1],
        mean=mean,
        min_value=min(values),
        max_value=max(values),
        delta=delta,
        direction=_direction(delta, mean),
    )


def _direction(delta: float, mean: float) -> str:
    """Traduce el cambio neto a una dirección legible, con banda muerta relativa a la media."""
    if mean and abs(delta) / abs(mean) < _STABLE_REL_BAND:
        return "estable"
    if delta > 0:
        return "subiendo"
    if delta < 0:
        return "bajando"
    return "estable"


# -------------------------------------------------------------------
# Tool 4 — get_medication_schedule
# -------------------------------------------------------------------

def get_medication_schedule(patient_id: str, data_dir: Path | None = None) -> list[Medication]:
    """
    Devuelve la medicación activa del paciente (nombre, dosis, frecuencia).

    Lee `medications.json` (mapa patient_id → lista). Devuelve [] si el paciente no figura.

    TO DO (B): mover a la fuente real (medicación base vive en el documento de Mongo del paciente).
    """
    base = data_dir or SAMPLE_DATA_DIR
    meds_path = base / "medications.json"
    if not meds_path.exists():
        return []

    data = json.loads(meds_path.read_text(encoding="utf-8"))
    return [Medication(**entry) for entry in data.get(patient_id, [])]


