# tools/mongo_tools.py
#
# Tools de MongoDB para el Agente Clínico.
# Operan sobre la colección "patients" (schema definido en data/load_mongo.py).
#
# get_patient_history        — historial acumulativo de sesiones previas (para C)
# compare_with_previous_sessions — compara métricas actuales con la sesión anterior (para C)
# update_patient_history     — guarda la sesión actual (solo con confirmación del médico)

from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "tp2_diabetes"
COLLECTION = "patients"


def _get_collection() -> Collection:
    client = MongoClient(MONGO_URI)
    return client[DB_NAME][COLLECTION]


# -------------------------------------------------------------------
# Tool 1 — get_patient_history
# -------------------------------------------------------------------

def get_patient_history(patient_id: str) -> dict:
    """
    Devuelve el documento completo del paciente desde MongoDB, incluyendo el
    historial de sesiones anteriores guardadas (`sessions`).

    Usado por el Agente Clínico para contexto longitudinal: comparaciones entre
    consultas, evolución del tratamiento, etc.

    Lanza ValueError si el paciente no existe en la base.
    """
    col = _get_collection()
    doc = col.find_one({"patient_id": patient_id}, {"_id": 0})
    if doc is None:
        raise ValueError(f"Paciente '{patient_id}' no encontrado en MongoDB")
    return doc


# -------------------------------------------------------------------
# Tool 2 — compare_with_previous_sessions
# -------------------------------------------------------------------

def compare_with_previous_sessions(
    patient_id: str,
    current_metrics: dict,
) -> dict:
    """
    Compara las métricas actuales con la sesión inmediatamente anterior guardada.

    `current_metrics` es un dict con las claves de métricas actuales
    (e.g. {"hba1c": 7.2, "glucose_fasting": 130.0, ...}).

    Devuelve un dict con:
      - previous_session: dict con fecha y métricas de la última sesión guardada
        (None si no hay sesiones previas).
      - deltas: dict métrica → diferencia (actual − anterior), solo para las
        métricas presentes en ambos dicts.
      - sessions_count: cuántas sesiones tiene el paciente en total.

    Si no hay sesiones previas, `previous_session` es None y `deltas` es {}.
    """
    doc = get_patient_history(patient_id)
    sessions = doc.get("sessions", [])

    if not sessions:
        return {
            "previous_session": None,
            "deltas": {},
            "sessions_count": 0,
        }

    last_session = sessions[-1]
    prev_metrics = last_session.get("metrics_summary", {})

    deltas = {
        metric: round(current_metrics[metric] - prev_metrics[metric], 4)
        for metric in current_metrics
        if metric in prev_metrics
    }

    return {
        "previous_session": {
            "date": last_session.get("date"),
            "metrics_summary": prev_metrics,
            "report_summary": last_session.get("report_summary"),
        },
        "deltas": deltas,
        "sessions_count": len(sessions),
    }


# -------------------------------------------------------------------
# Tool 3 — update_patient_history
# -------------------------------------------------------------------

def update_patient_history(
    patient_id: str,
    query: str,
    report: str,
    alerts: list[dict],
    metrics_summary: Optional[dict] = None,
) -> str:
    """
    Agrega la sesión actual al historial del paciente en MongoDB.

    IMPORTANTE: solo llamar con confirmación explícita del médico (el grafo
    lo controla con `awaiting_confirmation`; esta función no verifica eso).

    Parámetros:
      - patient_id: ID del paciente.
      - query: consulta del médico que disparó la sesión.
      - report: reporte generado por el Agente Clínico.
      - alerts: lista de alertas (dicts con metric, value, severity, date, description).
      - metrics_summary: dict opcional con valores clave de la sesión actual
        (e.g. {"hba1c": 7.2, "glucose_fasting": 130.0}); permite comparación futura.

    Devuelve el session_id asignado.
    """
    col = _get_collection()

    doc = col.find_one({"patient_id": patient_id}, {"_id": 0, "patient_id": 1})
    if doc is None:
        raise ValueError(f"Paciente '{patient_id}' no encontrado en MongoDB")

    session = {
        "session_id": str(uuid.uuid4()),
        "date": date.today().isoformat(),
        "saved_at": datetime.utcnow().isoformat(),
        "query": query,
        "report_summary": report[:500] if report else "",  # resumen corto para comparaciones
        "alerts": alerts,
        "metrics_summary": metrics_summary or {},
    }

    col.update_one(
        {"patient_id": patient_id},
        {"$push": {"sessions": session}},
    )

    return session["session_id"]
