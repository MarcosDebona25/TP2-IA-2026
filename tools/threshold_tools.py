# tools/threshold_tools.py
#
# Tool determinística del Agente Monitor: detección de violaciones de umbrales clínicos ADA.
# Sigue el mismo lineamiento que patient_tools.py (ver "Flujo de métricas" en docs/CLAUDE.md):
# se invoca por `patient_id` + `metric` + `timerange`, carga y recorta los datos con el helper
# de ventaneo único, y delega en un núcleo puro (`_detect_violations`) testeable con listas.
# Devuelve list[Alert] (modelo de orchestrator/state.py).
#
# Umbrales: tabla §2.6 de la def. conceptual (ADA). Cada métrica puede tener banda ALTA
# (hiperglucemia / diagnóstico) y/o banda BAJA (hipoglucemia):
#   ALTA:  valor >= `critico` → "severa" · valor >= `alerta` → "moderada"
#   BAJA:  valor <  `critico` → "severa" · valor <  `alerta` → "moderada"  (hipoglucemia)
#   en cualquier otro caso → normal (no genera alerta)
#
# Decisión de diseño (contrato A+C): se agregó la banda BAJA porque la vigilancia de
# HIPOglucemia es central en el seguimiento de un diabético, y la media la esconde (un episodio
# de 55 mg/dL "desaparece" en un promedio de ~88). Umbrales de hipoglucemia ADA: < 70 mg/dL
# (nivel 1, "moderada") y < 54 mg/dL (nivel 2, "severa"). HbA1c no tiene banda baja relevante.
#
# Notas:
#   - "leve" queda reservada: solo se emiten "moderada"/"severa", que son las que disparan
#     requires_rag en el Monitor.
#   - weight y presión arterial no tienen umbral en §2.6 → no se evalúan acá (devuelve []).

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from orchestrator.state import Alert, TimeRange
from tools.patient_tools import get_metric_series, load_patient_data, window_metrics

# -------------------------------------------------------------------
# Umbrales ADA (§2.6) — fuente única de verdad para esta tool
# -------------------------------------------------------------------

# metric -> {"label", "unit", "high": {alerta, critico}, "low": {alerta, critico}}
# "high" = hiperglucemia (valores altos); "low" = hipoglucemia (valores bajos). Ambas opcionales.
ADA_THRESHOLDS: dict[str, dict] = {
    "glucose_fasting": {
        "label": "glucosa en ayunas", "unit": "mg/dL",
        "high": {"alerta": 100.0, "critico": 126.0},
        "low":  {"alerta": 70.0,  "critico": 54.0},
    },
    "hba1c": {
        "label": "HbA1c", "unit": "%",
        "high": {"alerta": 5.7, "critico": 6.5},
    },
    "glucose_postprandial": {
        "label": "glucosa postprandial", "unit": "mg/dL",
        "high": {"alerta": 140.0, "critico": 200.0},
        "low":  {"alerta": 70.0,  "critico": 54.0},
    },
}


# -------------------------------------------------------------------
# Tool 3 — detect_threshold_violations  (wrapper) + núcleo puro
# -------------------------------------------------------------------

def detect_threshold_violations(
    patient_id: str,
    metric: str,
    timerange: Optional[TimeRange] = None,
    data_dir: Path | None = None,
) -> list[Alert]:
    """
    Violaciones de umbral ADA de `metric` para `patient_id` sobre la ventana `timerange`
    (global si None). Carga y recorta los datos (mismo ventaneo que calculate_stats) y delega
    en `_detect_violations`. Métricas sin umbral definido (peso, presión) devuelven [].
    """
    if metric not in ADA_THRESHOLDS:
        return []
    metrics = window_metrics(load_patient_data(patient_id, data_dir), timerange)
    values = get_metric_series(metrics, metric)
    return _detect_violations(metric, values, metrics.dates)


def _detect_violations(metric: str, values: list[float], dates: list[date]) -> list[Alert]:
    """
    Núcleo determinístico: compara cada valor contra los umbrales ADA de `metric` (bandas alta
    y/o baja) y devuelve una Alert por registro fuera de rango (con fecha, valor, severidad y
    descripción). `values` y `dates` deben tener el mismo largo (series alineadas).

    NOTA(contrato A+C): §2.6 definía `detect_threshold_violations(metric, values)`; Alert
    requiere la fecha del registro, así que el núcleo recibe `dates`. Ratificado por A y C.
    """
    thresholds = ADA_THRESHOLDS.get(metric)
    if thresholds is None:
        return []
    if len(values) != len(dates):
        raise ValueError(
            f"values ({len(values)}) y dates ({len(dates)}) deben tener el mismo largo para '{metric}'"
        )

    alertas: list[Alert] = []
    for value, registro_date in zip(values, dates):
        clasificacion = _classify(value, thresholds)
        if clasificacion is None:
            continue
        severity, side, umbral = clasificacion
        if side == "alta":
            desc = (f"{thresholds['label']} = {value} {thresholds['unit']} "
                    f"(umbral {severity}: ≥ {umbral} {thresholds['unit']})")
        else:  # "baja" → hipoglucemia
            desc = (f"{thresholds['label']} = {value} {thresholds['unit']} "
                    f"(hipoglucemia {severity}: < {umbral} {thresholds['unit']})")
        alertas.append(Alert(
            metric=metric, value=value, severity=severity, date=registro_date, description=desc,
        ))
    return alertas


def _classify(value: float, thresholds: dict) -> tuple[str, str, float] | None:
    """
    Clasifica un valor contra las bandas de la métrica. Devuelve (severidad, lado, umbral) o
    None si es normal. `lado` ∈ {"alta", "baja"}; severidad ∈ {"moderada", "severa"}.
    """
    high = thresholds.get("high")
    if high:
        if value >= high["critico"]:
            return ("severa", "alta", high["critico"])
        if value >= high["alerta"]:
            return ("moderada", "alta", high["alerta"])
    low = thresholds.get("low")
    if low:
        if value < low["critico"]:
            return ("severa", "baja", low["critico"])
        if value < low["alerta"]:
            return ("moderada", "baja", low["alerta"])
    return None
