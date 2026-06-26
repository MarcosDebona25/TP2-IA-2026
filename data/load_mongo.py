# data/load_mongo.py
#
# Carga los datos sintéticos de data/sample/ en MongoDB.
# Schema: una colección "patients"; un documento por paciente con su
# historial de métricas (array de registros mensuales) y medicación.
#
# Ejecutar: uv run python data/load_mongo.py
# Requiere: MONGO_URI en .env (default: mongodb://localhost:27017)

import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

load_dotenv()

# En Windows la consola usa cp1252 por defecto y no puede imprimir los caracteres
# Unicode de los mensajes (→, —). Forzar UTF-8 evita un UnicodeEncodeError al cargar.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "tp2_diabetes"
COLLECTION = "patients"

SAMPLE_DIR = Path(__file__).resolve().parent / "sample"
PATIENT_IDS = ["P001", "P002", "P003", "P004"]


def _load_csv(patient_id: str) -> list[dict]:
    path = SAMPLE_DIR / f"{patient_id}.csv"
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "date": row["date"],
                "glucose_fasting": float(row["glucose_fasting"]),
                "hba1c": float(row["hba1c"]),
                "glucose_postprandial": float(row["glucose_postprandial"]),
                "weight": float(row["weight"]),
                "blood_pressure_systolic": float(row["blood_pressure_systolic"]),
                "blood_pressure_diastolic": float(row["blood_pressure_diastolic"]),
            })
    return rows


def _load_medications() -> dict[str, list[dict]]:
    path = SAMPLE_DIR / "medications.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_patient_doc(patient_id: str, metrics: list[dict], medications: list[dict]) -> dict:
    """
    Schema del documento de paciente en MongoDB.

    {
      patient_id: str,               # clave de búsqueda (índice único)
      metrics_history: [             # una entrada por mes, orden cronológico
        { date, glucose_fasting, hba1c, glucose_postprandial,
          weight, blood_pressure_systolic, blood_pressure_diastolic }
      ],
      medications: [                 # medicación activa actual
        { name, dose, frequency }
      ],
      sessions: []                   # historial de sesiones guardadas (vacío al inicio;
                                     # update_patient_history() lo populará)
    }
    """
    return {
        "patient_id": patient_id,
        "metrics_history": metrics,
        "medications": medications,
        "sessions": [],
    }


def load_all(col: Collection) -> None:
    medications_map = _load_medications()
    for pid in PATIENT_IDS:
        metrics = _load_csv(pid)
        meds = medications_map.get(pid, [])
        doc = build_patient_doc(pid, metrics, meds)
        col.replace_one({"patient_id": pid}, doc, upsert=True)
        print(f"  {pid} — {len(metrics)} registro(s), {len(meds)} medicamento(s)")


def main() -> None:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION]
    col.create_index([("patient_id", ASCENDING)], unique=True)

    print(f"Conectado a {MONGO_URI} → {DB_NAME}.{COLLECTION}")
    load_all(col)
    print(f"Listo. Total documentos: {col.count_documents({})}")
    client.close()


if __name__ == "__main__":
    main()
