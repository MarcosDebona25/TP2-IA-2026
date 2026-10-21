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

import html
import json
from collections import deque
from pathlib import Path
from typing import Optional

from orchestrator.state import (
    Alert,
    Medication,
    MetricStats,
    MonitorAnalysis,
    PatientMetrics,
)
from agents.context import alert_groups
from tools.patient_tools import SAMPLE_DATA_DIR
from interface.logging_config import LOG_DIR, LOG_FILE

# Artefacto que produce tests/eval_runner.py y consume la pestaña "Evaluación".
EVAL_REPORT_FILE = LOG_DIR / "eval_report.json"

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

# Nombre y unidad por separado, para las tablas HTML (la unidad va en gris junto al nombre).
_METRIC_NAME_UNIT: dict[str, tuple[str, str]] = {
    "glucose_fasting": ("Glucosa en ayunas", "mg/dL"),
    "hba1c": ("HbA1c", "%"),
    "glucose_postprandial": ("Glucosa postprandial", "mg/dL"),
    "weight": ("Peso", "kg"),
    "blood_pressure_systolic": ("PA sistólica", "mmHg"),
    "blood_pressure_diastolic": ("PA diastólica", "mmHg"),
}

# Flecha + clase CSS por dirección de tendencia (output de MetricStats.direction).
_DIRECTION_ARROW = {"subiendo": "↑", "bajando": "↓", "estable": "→"}
_DIRECTION_CLASS = {"subiendo": "up", "bajando": "down", "estable": "flat"}

# Orden de severidad (output de Alert.severity): severa primero.
_SEVERITY_ORDER = {"severa": 0, "moderada": 1, "leve": 2}

_esc = html.escape


def _fmt(x: float) -> str:
    """Formatea un número con hasta 1 decimal, sin ceros sobrantes (5.40 → '5.4')."""
    return f"{x:.1f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def _fmt_signed(x: float) -> str:
    """Delta con signo explícito (+0.4 / −1.2 / 0), con el signo menos tipográfico."""
    if not x:
        return "0"
    return ("+" if x > 0 else "−") + _fmt(abs(x))


def _metric_cell(metric: str) -> str:
    name, unit = _METRIC_NAME_UNIT.get(metric, (metric, ""))
    unit_html = f"<span class='unit'>{_esc(unit)}</span>" if unit else ""
    return f"<td class='metric'>{_esc(name)}{unit_html}</td>"


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
    """Pill de severidad: color + texto (nunca solo color, por accesibilidad y proyector)."""
    sev = (severity or "").lower()
    cls = f"sev-{sev}" if sev in _SEVERITY_ORDER else "is-neutral"
    return f"<span class='tp2-pill {cls}'>{_esc(severity.capitalize())}</span>"


# -------------------------------------------------------------------
# Tabla de alertas
# -------------------------------------------------------------------

def _threshold_short(threshold: str) -> str:
    """Solo el comparador del umbral ("fuera de la meta…, moderada: >= 7 %" → "≥ 7 %")."""
    short = threshold.rsplit(": ", 1)[-1]
    return short.replace(">=", "≥").replace("<=", "≤")


def alerts_table(alerts: Optional[list[Alert]]) -> str:
    """
    Tabla HTML de alertas agrupadas, con el detalle de cada registro plegado debajo.
    `None` = todavía no hay análisis; `[]` = hubo análisis y no hay alertas (no confundirlos:
    "sin alertas" antes de analizar sería un falso negativo en pantalla).
    """
    if alerts is None:
        return "<p class='tp2-muted'>Las alertas aparecen después de analizar al paciente.</p>"
    if not alerts:
        return (
            "<div class='tp2-callout is-ok'><span class='tp2-pill is-ok'>Sin alertas</span>"
            "<span>No se detectaron valores fuera de las metas de control.</span></div>"
        )

    # Vista principal: un renglón por grupo (métrica + lado), con los MISMOS ids A1, A2… que usa
    # el reporte clínico, para que el médico cruce tabla y reporte sin buscar.
    grupos = []
    for g in alert_groups(alerts):
        pills = " ".join(severity_badge(s) for s in g.severities)
        nombre = _esc(g.title)
        unit = f"<span class='unit'>{_esc(g.unit)}</span>" if g.unit else ""
        grupos.append(
            "<tr>"
            f"<td class='id'>{g.id}</td>"
            f"<td class='metric'>{nombre}{unit}</td>"
            f"<td>{pills}</td>"
            f"<td class='num'>{g.count}</td>"
            f"<td class='num'><b>{_fmt(g.worst_value)}</b></td>"
            f"<td class='num'>{_esc(_threshold_short(g.threshold))}</td>"
            f"<td class='num period'>{_esc(g.period.replace(' a ', ' → '))}</td>"
            "</tr>"
        )

    # Detalle: cada registro fuera de meta, plegado para no ocupar la pantalla.
    alerts_ordenadas = sorted(alerts, key=lambda a: (_SEVERITY_ORDER.get(a.severity.lower(), 9), a.date))
    filas = []
    for a in alerts_ordenadas:
        filas.append(
            "<tr>"
            f"<td>{severity_badge(a.severity)}</td>"
            f"{_metric_cell(a.metric)}"
            f"<td class='num'>{_fmt(a.value)}</td>"
            f"<td class='num'>{a.date.isoformat()}</td>"
            f"<td class='desc'>{_esc(a.description)}</td>"
            "</tr>"
        )
    return (
        "<div class='tp2-table-wrap'><table class='tp2-table'>"
        "<thead><tr><th>Id</th><th>Métrica</th><th>Severidad</th><th class='num'>Registros</th>"
        "<th class='num'>Peor valor</th><th class='num'>Umbral</th><th class='num'>Período</th></tr></thead>"
        f"<tbody>{''.join(grupos)}</tbody></table></div>"
        f"<details class='tp2-disclosure'><summary>Ver los {len(alerts)} registros fuera de meta</summary>"
        "<div class='tp2-table-wrap'><table class='tp2-table'>"
        "<thead><tr><th>Severidad</th><th>Métrica</th><th class='num'>Valor</th>"
        "<th class='num'>Fecha</th><th>Detalle</th></tr></thead>"
        f"<tbody>{''.join(filas)}</tbody></table></div></details>"
    )


def alerts_meta(alerts: list[Alert]) -> str:
    """Resumen corto de alertas por severidad ("3 severas · 5 moderadas")."""
    if not alerts:
        return ""
    counts: dict[str, int] = {}
    for a in alerts:
        counts[a.severity.lower()] = counts.get(a.severity.lower(), 0) + 1
    plural = {"severa": "severas", "moderada": "moderadas", "leve": "leves"}
    partes = [
        f"{n} {sev if n == 1 else plural.get(sev, sev)}"
        for sev, n in sorted(counts.items(), key=lambda kv: _SEVERITY_ORDER.get(kv[0], 9))
    ]
    return " · ".join(partes)


# -------------------------------------------------------------------
# Visualización de tendencias
# -------------------------------------------------------------------

def _trend_row(metric: str, stats: Optional[MetricStats]) -> str:
    if stats is None:  # métrica sin registros: no se inventan valores (ADR-0003)
        return f"<tr>{_metric_cell(metric)}" + "<td class='num na'>—</td>" * 5 + "<td class='na'>sin datos</td></tr>"
    arrow = _DIRECTION_ARROW.get(stats.direction, "")
    cls = _DIRECTION_CLASS.get(stats.direction, "flat")
    return (
        f"<tr>{_metric_cell(metric)}"
        f"<td class='num'><b>{_fmt(stats.last_value)}</b></td>"
        f"<td class='num'>{_fmt(stats.mean)}</td>"
        f"<td class='num'>{_fmt(stats.min_value)}</td>"
        f"<td class='num'>{_fmt(stats.max_value)}</td>"
        f"<td class='num'>{_fmt_signed(stats.delta)}</td>"
        f"<td><span class='tp2-dir {cls}'>{arrow} {_esc(stats.direction)}</span></td></tr>"
    )


def trends_view(analysis: Optional[MonitorAnalysis]) -> str:
    """
    Tabla HTML con las estadísticas por métrica (último, media, mín, máx, Δ, tendencia).
    Devuelve un aviso si todavía no hay análisis del Monitor, y lista las métricas con datos
    insuficientes para evaluar su evolución.
    """
    if analysis is None:
        return "<p class='tp2-muted'>Las tendencias aparecen después de analizar al paciente.</p>"

    filas = [
        _trend_row("glucose_fasting", analysis.glucose_fasting_stats),
        _trend_row("hba1c", analysis.hba1c_stats),
        _trend_row("glucose_postprandial", analysis.glucose_postprandial_stats),
        _trend_row("weight", analysis.weight_stats),
        _trend_row("blood_pressure_systolic", analysis.blood_pressure_stats.systolic),
        _trend_row("blood_pressure_diastolic", analysis.blood_pressure_stats.diastolic),
    ]
    out = [
        "<div class='tp2-table-wrap'><table class='tp2-table'>"
        "<thead><tr><th>Métrica</th><th class='num'>Último</th><th class='num'>Media</th>"
        "<th class='num'>Mín</th><th class='num'>Máx</th><th class='num'>Δ</th><th>Tendencia</th></tr></thead>"
        f"<tbody>{''.join(filas)}</tbody></table></div>"
    ]
    if analysis.insufficient_data:
        items = "".join(
            f"<li>{_esc(METRIC_LABELS.get(metric, metric))}: {_esc(str(motivo))}</li>"
            for metric, motivo in analysis.insufficient_data.items()
        )
        out.append(
            "<div class='tp2-callout'><div><b>Datos insuficientes para evaluar la evolución</b>"
            f"<ul>{items}</ul></div></div>"
        )
    return "".join(out)


# -------------------------------------------------------------------
# Indicadores clave (franja de resumen sobre el reporte)
# -------------------------------------------------------------------

def _kpi(label: str, value: str, unit: str = "", foot: str = "", cls: str = "") -> str:
    unit_html = f"<small>{_esc(unit)}</small>" if unit else ""
    return (
        f"<div class='tp2-kpi {cls}'><p class='tp2-kpi-label'>{_esc(label)}</p>"
        f"<p class='tp2-kpi-value'>{value}{unit_html}</p>"
        f"<p class='tp2-kpi-foot'>{foot}</p></div>"
    )


def _kpi_metric(label: str, unit: str, stats: Optional[MetricStats]) -> str:
    if stats is None:
        return _kpi(label, "—", foot="sin registros")
    arrow = _DIRECTION_ARROW.get(stats.direction, "")
    cls = _DIRECTION_CLASS.get(stats.direction, "flat")
    foot = (f"<span class='tp2-dir {cls}'>{arrow} {_esc(stats.direction)}</span>"
            f"<span>Δ {_fmt_signed(stats.delta)} · media {_fmt(stats.mean)}</span>")
    return _kpi(label, _fmt(stats.last_value), unit, foot)


def summary_strip(analysis: Optional[MonitorAnalysis]) -> str:
    """
    Franja de indicadores del análisis: alertas por severidad y último valor de HbA1c, glucosa en
    ayunas y presión arterial, con su tendencia. Solo muestra valores del análisis (ADR-0003):
    una métrica sin registros se ve como "—". Antes del análisis muestra las mismas tarjetas
    vacías, para que el layout no salte al llegar los resultados.
    """
    if analysis is None:
        vacias = "".join(_kpi(label, "—", foot="sin análisis")
                         for label in ("Alertas", "HbA1c", "Glucosa en ayunas", "Presión arterial"))
        return f"<div class='tp2-kpis is-empty'>{vacias}</div>"

    severas = sum(1 for a in analysis.alerts if a.severity.lower() == "severa")
    total = len(analysis.alerts)
    if total:
        alerts_kpi = _kpi("Alertas", str(total), foot=f"<span>{_esc(alerts_meta(analysis.alerts))}</span>",
                          cls="is-high" if severas else "")
    else:
        alerts_kpi = _kpi("Alertas", "0", foot="dentro de metas", cls="is-ok")

    bp = analysis.blood_pressure_stats
    if bp.systolic and bp.diastolic:
        arrow = _DIRECTION_ARROW.get(bp.systolic.direction, "")
        cls = _DIRECTION_CLASS.get(bp.systolic.direction, "flat")
        bp_kpi = _kpi(
            "Presión arterial", f"{_fmt(bp.systolic.last_value)}/{_fmt(bp.diastolic.last_value)}", "mmHg",
            f"<span class='tp2-dir {cls}'>{arrow} sistólica {_esc(bp.systolic.direction)}</span>",
        )
    else:
        bp_kpi = _kpi("Presión arterial", "—", foot="sin registros")

    return (
        "<div class='tp2-kpis'>"
        + alerts_kpi
        + _kpi_metric("HbA1c", "%", analysis.hba1c_stats)
        + _kpi_metric("Glucosa en ayunas", "mg/dL", analysis.glucose_fasting_stats)
        + bp_kpi
        + "</div>"
    )


# -------------------------------------------------------------------
# Perfil resumido del paciente
# -------------------------------------------------------------------

_FALLBACK_MOTIVOS = {
    "rate_limit": "se agotó la cuota del proveedor del LLM (límite de tokens)",
    "too_large": "el pedido superó el tamaño que admite el modelo",
    "no_api_key": "no hay API key de LLM configurada en .env",
    "error": "el LLM devolvió un error (ver logs/agent.jsonl)",
}


def execution_warning(execution_mode: Optional[dict]) -> str:
    """
    Aviso visible cuando algún agente cayó al fallback determinístico (F3-06). Devuelve "" si todos
    los nodos usaron el LLM. Sin esto, una cuota agotada se ve como un reporte pobre sin explicación.
    """
    caidos = {node: mode for node, mode in (execution_mode or {}).items() if str(mode).startswith("fallback")}
    if not caidos:
        return ""
    motivos = {m.split(":", 1)[1] if ":" in m else "error" for m in caidos.values()}
    detalle = "; ".join(_FALLBACK_MOTIVOS.get(m, _FALLBACK_MOTIVOS["error"]) for m in sorted(motivos))
    nodos = " y ".join(sorted(caidos))
    return (f"**Modo determinístico: el LLM no respondió ({nodos})**, {detalle}. Lo que ves es el "
            "resultado básico de las tools, sin interpretación clínica. Probá de nuevo en unos minutos.")


_SEX_LABELS = {"M": "Masculino", "F": "Femenino"}


def patient_profile(
    patient_id: str,
    metrics: Optional[PatientMetrics],
    medication: Optional[list[Medication]],
    history: Optional[dict] = None,
) -> str:
    """
    Ficha HTML del paciente para mostrar ANTES de lanzar el análisis (paso 2 del flujo).
    Combina el perfil del historial (demografía, diagnósticos, comorbilidades, sesiones previas),
    lo disponible del EHR (rango de fechas, último peso/PA) y la medicación activa.
    Degrada con elegancia si faltan datos.
    """
    if not patient_id:
        return "<p class='tp2-muted'>Elegí un paciente para ver su ficha.</p>"

    sub = "Sin perfil en el historial"
    filas: list[tuple[str, str]] = []

    if history and history.get("found"):
        demo = history.get("demographics") or {}
        if demo:
            sexo = _SEX_LABELS.get(str(demo.get("sex", "")), demo.get("sex", "?"))
            sub = f"{demo.get('age', '?')} años · {sexo}"
        diagnoses = history.get("diagnoses") or []
        if diagnoses:
            filas.append(("Diagnóstico", "<br>".join(
                f"{_esc(str(d.get('label')))} <small>{_esc(str(d.get('code')))} · desde {_esc(str(d.get('since')))}</small>"
                for d in diagnoses
            )))
        comorbidities = history.get("comorbidities") or []
        filas.append(("Comorbilidades", (
            "<div class='tp2-chips'>" + "".join(f"<span class='tp2-chip'>{_esc(c)}</span>" for c in comorbidities)
            + "</div>") if comorbidities else "<small>ninguna registrada</small>"))
        sessions = history.get("sessions") or []
        if sessions:
            filas.append(("Sesiones previas",
                          f"{len(sessions)} <small>· última {_esc(str(sessions[-1].get('date', '?')))}</small>"))

    if metrics and metrics.dates:
        filas.append(("Registros EHR", f"{len(metrics.dates)} <small>· {metrics.dates[0].isoformat()} → "
                                       f"{metrics.dates[-1].isoformat()}</small>"))
        if metrics.weight:
            filas.append(("Último peso", f"{_fmt(metrics.weight[-1])} <small>kg</small>"))
        if metrics.blood_pressure_systolic and metrics.blood_pressure_diastolic:
            filas.append(("Última PA", f"{_fmt(metrics.blood_pressure_systolic[-1])}/"
                                       f"{_fmt(metrics.blood_pressure_diastolic[-1])} <small>mmHg</small>"))
    else:
        filas.append(("Registros EHR", "<small>sin datos cargados para este paciente</small>"))

    if medication:
        filas.append(("Medicación", "<br>".join(
            f"{_esc(m.name)} {_esc(m.dose)} <small>· {_esc(m.frequency)}</small>" for m in medication
        )))
    else:
        filas.append(("Medicación", "<small>sin registros</small>"))

    iniciales = _esc(patient_id[-3:] if len(patient_id) > 3 else patient_id)
    kv = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in filas)
    return (
        "<div class='tp2-patient'>"
        f"<div class='tp2-patient-head'><div class='tp2-avatar'>{iniciales}</div><div>"
        f"<p class='tp2-patient-id'>Paciente {_esc(patient_id)}</p>"
        f"<p class='tp2-patient-sub'>{_esc(sub)}</p></div></div>"
        f"<dl class='tp2-kv'>{kv}</dl></div>"
    )


# -------------------------------------------------------------------
# Reporte clínico (panel principal)
# -------------------------------------------------------------------

def format_report(report: Optional[str]) -> str:
    """Formatea el reporte del Agente Clínico para el panel principal."""
    if not report:
        return (
            "<div class='tp2-empty-state'>"
            "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.6' "
            "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
            "<path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/>"
            "<path d='M14 3v5h5M9 13h6M9 17h4'/></svg>"
            "<h4>Todavía no hay un reporte</h4>"
            "<p>El reporte clínico aparece acá cuando termina el análisis.</p>"
            "<ul class='tp2-steps'><li><b>1</b>Elegí un paciente</li>"
            "<li><b>2</b>Sumá contexto (opcional)</li><li><b>3</b>Analizar paciente</li></ul>"
            "</div>"
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

    group = event_filter if event_filter not in (None, "todos", "all") else None

    # Tail acotado: conservamos solo las últimas `limit` entradas (ya filtradas) con un
    # deque de tamaño fijo. Así la memoria queda acotada y no materializamos miles de dicts
    # aunque el .jsonl haya crecido hasta el tope de rotación (5 MB).
    kept: deque[dict] = deque(maxlen=limit)
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if group and _event_group(entry.get("event", "")) != group:
                continue
            kept.append(entry)

    kept.reverse()  # más recientes primero
    return list(kept)


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
        return f"Error: {entry.get('error', '')}"
    return name


def _event_class(event: str) -> str:
    """Clase CSS del tag de evento en el visor (errores, llamadas al LLM, tools)."""
    if event.endswith("_error"):
        return "ev-error"
    group = _event_group(event)
    return f"ev-{group}" if group in ("llm", "tool") else ""


# Largo máximo del texto que se muestra en el resumen colapsado de cada fila. El detalle
# completo (input/output de tools, prompts y respuestas del LLM) queda en el JSON crudo que
# se despliega al expandir la fila, así que acá solo acotamos lo que se ve de un vistazo.
_CELL_MAX = 120


def _clip(text: str, n: int = _CELL_MAX) -> str:
    """Recorta un texto a `n` caracteres para mostrarlo en el resumen de una fila."""
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def log_view_html(entries: list[dict]) -> str:
    """
    Render del visor de logs como HTML plano (clase `tp2-logs`, estilada en interface/app.py).

    Cada entrada es un `<details>`: el `<summary>` muestra hora/evento/componente/resumen en
    una grilla (como una tabla) y, al expandirlo, aparece el JSON crudo completo en un `<pre>`.

    Reemplaza al antiguo gr.Dataframe a propósito: el Dataframe es un widget de planilla
    editable que tardaba ~15 s en montarse en el navegador al abrir la pestaña. Un bloque de
    HTML estático con `<details>` se pinta en milisegundos y no necesita gr.State ni un
    segundo viaje al servidor para ver el detalle (va inline). Tolera la lista vacía.
    """
    if not entries:
        return (
            "<div class='tp2-logs'><div class='tp2-empty'>"
            "Sin trazas registradas todavía. Ejecutá un análisis y volvé a refrescar."
            "</div></div>"
        )

    out = [
        "<div class='tp2-logs'>",
        "<div class='tp2-head'>"
        "<span>Hora</span><span>Evento</span><span>Componente</span><span>Resumen</span>"
        "</div>",
    ]
    for e in entries:
        ts = html.escape((e.get("ts") or "")[11:23])  # solo HH:MM:SS.mmm
        ev_cls = _event_class(e.get("event", ""))
        event = html.escape(e.get("event", ""))
        name = html.escape(_clip(e.get("name", "")))
        summary = html.escape(_clip(_summarize_entry(e)))
        raw = html.escape(json.dumps(e, ensure_ascii=False, indent=2, default=str))
        out.append(
            "<details class='tp2-row'><summary><div class='tp2-cells'>"
            f"<span class='tp2-ts'>{ts}</span>"
            f"<span class='tp2-ev {ev_cls}'>{event}</span>"
            f"<span class='tp2-nm' title=\"{name}\">{name}</span>"
            f"<span class='tp2-sm' title=\"{summary}\">{summary}</span>"
            "</div></summary>"
            f"<pre class='tp2-raw'>{raw}</pre></details>"
        )
    out.append("</div>")
    return "".join(out)


# -------------------------------------------------------------------
# Visor de evaluación cualitativa (pestaña "Evaluación")
# -------------------------------------------------------------------
#
# Lee el artefacto JSON que produce tests/eval_runner.py (logs/eval_report.json): un HISTORIAL
# de corridas (array de objetos-corrida). Cada corrida tiene su propio set de casos evaluados.
# La UI ofrece un selector de corrida + un selector de caso, y compara "esperado vs. obtenido".
# Como el resto del módulo, son funciones puras (string in → string out), testeables sin Gradio.

# Etiqueta legible por categoría de caso (las 3 del enunciado).
EVAL_CATEGORY_LABELS: dict[str, str] = {
    "happy_path": "Happy path",
    "edge_cases": "Edge case",
    "adversarial": "Adversarial",
}

_RUN_HINT = (
    "Generá el artefacto con `uv run python tests/eval_runner.py` "
    "(requiere API key del LLM) y volvé a refrescar."
)


# Marcador por status de la corrida de un caso. "degraded" = el LLM falló y el grafo cayó al
# fallback determinístico (la salida no refleja al modelo); "error" = el caso crasheó entero.
_STATUS_MARK = {"ok": "", "degraded": "degradado", "error": "error"}


def _category_label(category: str) -> str:
    return EVAL_CATEGORY_LABELS.get(category, category)


def _case_status(case: dict) -> str:
    """Status del caso, con fallback para artefactos viejos sin el campo `status`."""
    st = case.get("status")
    if st:
        return st
    return "error" if case.get("error") else "ok"


def _status_counts(cases: list[dict]) -> dict[str, int]:
    """Cuenta casos por status (ok / degraded / error)."""
    counts = {"ok": 0, "degraded": 0, "error": 0}
    for c in cases:
        counts[_case_status(c)] = counts.get(_case_status(c), 0) + 1
    return counts


def load_eval_history(path: Path | None = None) -> list[dict]:
    """
    Lee el historial de evaluación (logs/eval_report.json) y lo devuelve como lista de corridas.

    Devuelve [] si el archivo no existe o está corrupto. Migra el formato viejo (un único
    objeto-reporte) envolviéndolo en una lista de una corrida, para no romper artefactos previos.
    """
    report_path = path or EVAL_REPORT_FILE
    if not report_path.exists():
        return []
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):  # formato viejo (un solo reporte) → una corrida
        return [data]
    return []


def eval_history_summary_md(history: list[dict] | None) -> str:
    """Encabezado del historial: cuántas corridas hay y cuándo fue la última."""
    if not history:
        return "_Todavía no hay corridas de evaluación._\n\n" + _RUN_HINT
    ultima = history[-1]
    return (
        f"**Historial de evaluación** — {len(history)} corrida(s) registrada(s) · "
        f"última: {ultima.get('generated_at', '?')} (`{ultima.get('model', '?')}`)"
    )


def eval_run_choices(history: list[dict] | None) -> list[tuple[str, int]]:
    """Opciones (label, índice) para el selector de corridas, más recientes primero."""
    if not history:
        return []
    choices = []
    for i, run in enumerate(history):
        n_casos = run.get("case_count", len(run.get("cases", [])))
        counts = _status_counts(run.get("cases", []))
        flags = []
        if counts["degraded"]:
            flags.append(f"{counts['degraded']} degradado(s)")
        if counts["error"]:
            flags.append(f"{counts['error']} con error")
        flag = f" · {' · '.join(flags)}" if flags else ""
        label = (
            f"#{i + 1} · {run.get('generated_at', '?')} · "
            f"{run.get('model', '?')} · {n_casos} caso(s){flag}"
        )
        choices.append((label, i))
    choices.reverse()  # la corrida más reciente arriba
    return choices


def get_eval_run(history: list[dict] | None, run_idx: int | None) -> Optional[dict]:
    """Devuelve la corrida en ese índice (o la última si no se especifica o es inválido)."""
    if not history:
        return None
    if run_idx is None:
        return history[-1]
    try:
        return history[int(run_idx)]
    except (IndexError, ValueError, TypeError):
        return history[-1]


def eval_summary_md(report: Optional[dict]) -> str:
    """Cabecera con los metadatos de una corrida y el desglose por categoría."""
    if not report:
        return (
            "_Todavía no hay resultados de evaluación._\n\n" + _RUN_HINT
        )

    cases = report.get("cases", [])
    por_categoria = {cat: 0 for cat in EVAL_CATEGORY_LABELS}
    for c in cases:
        por_categoria[c.get("category", "")] = por_categoria.get(c.get("category", ""), 0) + 1
    desglose = " · ".join(
        f"{_category_label(cat)}: {n}" for cat, n in por_categoria.items() if n
    )

    counts = _status_counts(cases)
    flags = []
    if counts["degraded"]:
        flags.append(f"{counts['degraded']} degradado(s) al fallback")
    if counts["error"]:
        flags.append(f"{counts['error']} con error")
    estado = " · " + " · ".join(flags) if flags else " · sin incidencias"

    return (
        f"**Evaluación cualitativa** — {len(cases)} caso(s) · "
        f"proveedor `{report.get('provider', '?')}` · modelo `{report.get('model', '?')}`  \n"
        f"Generado: {report.get('generated_at', '?')}  \n"
        f"{desglose}{estado}"
    )


def eval_case_choices(report: Optional[dict]) -> list[tuple[str, str]]:
    """Opciones (label, id) para el selector de casos, en el orden del reporte."""
    if not report:
        return []
    choices = []
    for c in report.get("cases", []):
        desc = _clip(c.get("description", ""), 56)
        categoria = _category_label(c.get("category", ""))
        mark = _STATUS_MARK.get(_case_status(c), "")
        suffix = f" · {mark}" if mark else ""
        choices.append((f"{c.get('id', '?')} — {desc} [{categoria}]{suffix}", c.get("id", "")))
    return choices


def find_eval_case(report: Optional[dict], case_id: str | None) -> Optional[dict]:
    """Devuelve el caso con ese id (o el primero si no se especifica) del reporte."""
    if not report:
        return None
    cases = report.get("cases", [])
    if not cases:
        return None
    if case_id:
        for c in cases:
            if c.get("id") == case_id:
                return c
    return cases[0]


def eval_context_md(case: Optional[dict]) -> str:
    """Tira de contexto del caso: categoría, descripción, setup e input."""
    if not case:
        return "_Seleccioná un caso para ver la comparación._"

    lineas = [
        f"#### {_category_label(case.get('category', ''))} · `{case.get('id', '?')}`",
        case.get("description", ""),
    ]
    if case.get("setup"):
        pasos = "; ".join(json.dumps(s, ensure_ascii=False) for s in case["setup"])
        lineas.append(f"- **Setup previo:** {pasos}")
    lineas.append(f"- **Input:** `{json.dumps(case.get('input', {}), ensure_ascii=False)}`")

    meta = []
    if case.get("alerts_count") is not None:
        meta.append(f"alertas: {case['alerts_count']}")
    if case.get("duration_s") is not None:
        meta.append(f"{case['duration_s']} s")
    if case.get("model"):
        meta.append(f"modelo `{case['model']}`")
    if case.get("evaluated_at"):
        meta.append(f"corrido: {case['evaluated_at']}")
    if meta:
        lineas.append(f"- _{' · '.join(meta)}_")

    return "\n".join(lineas)


def eval_expected_md(case: Optional[dict]) -> str:
    """Panel izquierdo: el comportamiento esperado del caso."""
    if not case:
        return ""
    return case.get("expected_behavior", "_(sin comportamiento esperado definido)_")


def eval_obtained_md(case: Optional[dict]) -> str:
    """Panel derecho: la salida obtenida del sistema (reporte/respuesta del Clínico)."""
    if not case:
        return ""

    status = _case_status(case)
    if status == "error":
        return f"**Error durante la ejecución del caso**\n\n```\n{case.get('error', '')}\n```"

    parts = []
    if status == "degraded":
        # El LLM falló y el grafo cayó al fallback determinístico: la salida de abajo NO refleja
        # al modelo, así que avisamos antes de mostrarla para no puntuarla como si fuera del LLM.
        parts.append(
            "> **Salida degradada: fallback determinístico, no refleja al LLM.**  \n"
            "El modelo falló durante la corrida (rate limit, 413, timeout…) y el grafo respondió "
            "con su fallback sin LLM. Volvé a correr el caso con más cupo de tokens.\n\n"
            f"_Motivo:_\n```\n{case.get('error', '')}\n```"
        )
    obtained = case.get("obtained")
    if obtained:
        parts.append(obtained)
    return "\n\n".join(parts) if parts else "_(sin salida)_"


def eval_case_view(
    report: Optional[dict], case_id: str | None
) -> tuple[str, str, str]:
    """Render completo de un caso: (contexto, esperado, obtenido). Atajo para el wiring."""
    case = find_eval_case(report, case_id)
    return eval_context_md(case), eval_expected_md(case), eval_obtained_md(case)
