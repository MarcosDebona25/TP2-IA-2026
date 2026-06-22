# interface/components.py
#
# Componentes de presentación reutilizables de la UI (tarea del Integrante D).
#
# Son funciones PURAS: reciben los modelos Pydantic de orchestrator/state.py (o datos del log)
# y devuelven Markdown/HTML como string. No dependen de Gradio → se pueden testear sin levantar
# la interfaz y se reusan tanto en interface/app.py como en los tests del Fragmento 3.
#
# Toleran datos faltantes (analysis=None, métricas sin CSV, log vacío): la UI no debe romperse
# si un paciente no tiene datos de EHR todavía (p. ej. mientras B no entrega el dataset real).

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from orchestrator.state import (
    Alert,
    Medication,
    MetricStats,
    MonitorAnalysis,
    PatientMetrics,
)
from tools.patient_tools import SAMPLE_DATA_DIR
from interface.logging_config import LOG_FILE

# -------------------------------------------------------------------
# Etiquetas legibles y formato
# -------------------------------------------------------------------

# Nombre clínico legible de cada métrica (con su unidad).
METRIC_LABELS: dict[str, str] = {
    "glucose_fasting": "Glucosa en ayunas (mg/dL)",
    "hba1c": "HbA1c (%)",
    "glucose_postprandial": "Glucosa postprandial (mg/dL)",
    "weight": "Peso (kg)",
    "blood_pressure_systolic": "PA sistólica (mmHg)",
    "blood_pressure_diastolic": "PA diastólica (mmHg)",
}

# Flecha por dirección de tendencia (output de MetricStats.direction).
_DIRECTION_ARROW = {"subiendo": "↑", "bajando": "↓", "estable": "→"}

# Emoji por severidad (output de Alert.severity).
_SEVERITY_EMOJI = {"severa": "🔴", "moderada": "🟠", "leve": "🟡"}


def _fmt(x: float) -> str:
    """Formatea un número con hasta 1 decimal, sin ceros sobrantes (5.40 → '5.4')."""
    return f"{x:.1f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


# -------------------------------------------------------------------
# Selector de pacientes
# -------------------------------------------------------------------

def list_patients(data_dir: Path | None = None) -> list[str]:
    """
    IDs de pacientes disponibles, derivados de los CSV del EHR (`data/sample/*.csv`).
    Dinámico a propósito: cuando B reemplace el fixture por el dataset real, el selector
    de la UI se actualiza solo. Devuelve [] si no hay datos.
    """
    base = data_dir or SAMPLE_DATA_DIR
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.csv"))


# -------------------------------------------------------------------
# Badge de severidad
# -------------------------------------------------------------------

def severity_badge(severity: str) -> str:
    """Devuelve un badge legible (emoji + texto) para una severidad de alerta."""
    emoji = _SEVERITY_EMOJI.get(severity.lower(), "⚪")
    return f"{emoji} {severity.capitalize()}"


# -------------------------------------------------------------------
# Tabla de alertas
# -------------------------------------------------------------------

def alerts_table(alerts: list[Alert]) -> str:
    """Tabla Markdown de alertas, ordenadas por severidad (severa → moderada → leve)."""
    if not alerts:
        return "✅ **Sin alertas**: no se detectaron violaciones de umbrales clínicos."

    orden = {"severa": 0, "moderada": 1, "leve": 2}
    alerts_ordenadas = sorted(alerts, key=lambda a: orden.get(a.severity.lower(), 9))

    filas = [
        "| Severidad | Métrica | Valor | Fecha | Detalle |",
        "|---|---|---|---|---|",
    ]
    for a in alerts_ordenadas:
        metrica = METRIC_LABELS.get(a.metric, a.metric)
        filas.append(
            f"| {severity_badge(a.severity)} | {metrica} | {_fmt(a.value)} | {a.date.isoformat()} | {a.description} |"
        )
    return "\n".join(filas)


# -------------------------------------------------------------------
# Visualización de tendencias
# -------------------------------------------------------------------

def _trend_row(label: str, stats: MetricStats) -> str:
    arrow = _DIRECTION_ARROW.get(stats.direction, "")
    return (
        f"| {label} | {_fmt(stats.last_value)} | {_fmt(stats.mean)} | "
        f"{_fmt(stats.min_value)} | {_fmt(stats.max_value)} | {_fmt(stats.delta):>4} | "
        f"{arrow} {stats.direction} |"
    )


def trends_view(analysis: Optional[MonitorAnalysis]) -> str:
    """
    Tabla Markdown con las estadísticas por métrica (último, media, mín, máx, Δ, tendencia).
    Devuelve un aviso si todavía no hay análisis del Monitor.
    """
    if analysis is None:
        return "_Sin análisis del Monitor todavía. Ejecutá un análisis para ver las tendencias._"

    filas = [
        "| Métrica | Último | Media | Mín | Máx | Δ | Tendencia |",
        "|---|---|---|---|---|---|---|",
        _trend_row(METRIC_LABELS["glucose_fasting"], analysis.glucose_fasting_stats),
        _trend_row(METRIC_LABELS["hba1c"], analysis.hba1c_stats),
        _trend_row(METRIC_LABELS["glucose_postprandial"], analysis.glucose_postprandial_stats),
        _trend_row(METRIC_LABELS["weight"], analysis.weight_stats),
        _trend_row(METRIC_LABELS["blood_pressure_systolic"], analysis.blood_pressure_stats.systolic),
        _trend_row(METRIC_LABELS["blood_pressure_diastolic"], analysis.blood_pressure_stats.diastolic),
    ]
    return "\n".join(filas)


# -------------------------------------------------------------------
# Perfil resumido del paciente
# -------------------------------------------------------------------

def patient_profile(
    patient_id: str,
    metrics: Optional[PatientMetrics],
    medication: Optional[list[Medication]],
) -> str:
    """
    Resumen del paciente para mostrar ANTES de lanzar el análisis (paso 2 del flujo).
    Combina lo disponible del EHR (rango de fechas, último peso/PA) con la medicación activa.
    Degrada con elegancia si faltan datos.
    """
    if not patient_id:
        return "_Seleccioná un paciente para ver su perfil._"

    lineas = [f"### Paciente {patient_id}"]

    if metrics and metrics.dates:
        n = len(metrics.dates)
        lineas.append(
            f"- **Registros EHR**: {n} ({metrics.dates[0].isoformat()} → {metrics.dates[-1].isoformat()})"
        )
        if metrics.weight:
            lineas.append(f"- **Último peso**: {_fmt(metrics.weight[-1])} kg")
        if metrics.blood_pressure_systolic and metrics.blood_pressure_diastolic:
            lineas.append(
                f"- **Última PA**: {_fmt(metrics.blood_pressure_systolic[-1])}/"
                f"{_fmt(metrics.blood_pressure_diastolic[-1])} mmHg"
            )
    else:
        lineas.append("- _Sin datos de EHR cargados para este paciente._")

    if medication:
        meds = ", ".join(f"{m.name} {m.dose} ({m.frequency})" for m in medication)
        lineas.append(f"- **Medicación activa**: {meds}")
    else:
        lineas.append("- **Medicación activa**: sin registros")

    return "\n".join(lineas)


# -------------------------------------------------------------------
# Reporte clínico (panel principal)
# -------------------------------------------------------------------

def format_report(report: Optional[str]) -> str:
    """Formatea el reporte del Agente Clínico para el panel principal."""
    if not report:
        return (
            "_El reporte clínico aparecerá acá tras ejecutar el análisis._\n\n"
            "1. Seleccioná un paciente · 2. (Opcional) Agregá contexto clínico · "
            "3. Presioná **Analizar paciente**."
        )
    return report


# -------------------------------------------------------------------
# Visor de logs (pestaña de observabilidad)
# -------------------------------------------------------------------

# Grupo de evento → predicado, para el filtro de la pestaña dev.
_EVENT_GROUPS: dict[str, str] = {
    "node": "node_start",
    "routing": "routing",
    "llm": "llm",
    "tool": "tool",
}


def _event_group(event: str) -> str:
    """Clasifica un `event` del log en un grupo legible (node/routing/llm/tool/otro)."""
    if event == "node_start":
        return "node"
    if event == "routing":
        return "routing"
    if event.startswith("llm"):
        return "llm"
    if event.startswith("tool"):
        return "tool"
    return "otro"


def load_log_entries(
    event_filter: Optional[str] = None,
    path: Path | None = None,
    limit: int = 500,
) -> list[dict]:
    """
    Lee `logs/agent.jsonl` y devuelve las entradas (dicts), más recientes primero.

    - `event_filter`: None/"todos" → todas; "node"/"routing"/"llm"/"tool" → solo ese grupo.
    - Tolera líneas corruptas/parciales (las saltea) y archivo inexistente (devuelve []).
    """
    log_path = path or LOG_FILE
    if not log_path.exists():
        return []

    entries: list[dict] = []
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if event_filter and event_filter not in ("todos", "all"):
        entries = [e for e in entries if _event_group(e.get("event", "")) == event_filter]

    entries.reverse()  # más recientes primero
    return entries[:limit]


def _summarize_entry(entry: dict) -> str:
    """Resumen de una línea de log para la columna 'resumen' de la tabla."""
    event = entry.get("event", "")
    name = entry.get("name", "")
    if event == "routing":
        return f"{name} → nodo {entry.get('node', '?')}"
    if event == "llm_start":
        n = len(entry.get("prompts") or entry.get("messages") or [])
        return f"{name} · {n} prompt(s)"
    if event == "llm_end":
        tokens = entry.get("tokens")
        return f"{len(entry.get('responses') or [])} respuesta(s)" + (f" · tokens={tokens}" if tokens else "")
    if event == "tool_start":
        return f"{name} · input={entry.get('input', '')}"
    if event == "tool_end":
        return f"output={entry.get('output', '')}"
    if event in ("llm_error", "tool_error"):
        return f"⚠️ {entry.get('error', '')}"
    return name


def log_entries_to_rows(entries: list[dict]) -> list[list[str]]:
    """Convierte las entradas del log en filas para un gr.Dataframe: [hora, evento, nombre, resumen]."""
    rows: list[list[str]] = []
    for e in entries:
        ts = (e.get("ts") or "")[11:23]  # solo HH:MM:SS.mmm
        rows.append([ts, e.get("event", ""), e.get("name", ""), _summarize_entry(e)])
    return rows
