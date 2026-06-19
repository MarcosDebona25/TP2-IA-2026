# tests/test_tools.py
#
# Pruebas unitarias para las herramientas stubs de MongoDB y RAG.

import pytest

from tools.patient_tools import compare_with_previous_sessions, get_patient_history
from tools.rag_tools import search_clinical_guidelines


def test_get_patient_history():
    # Paciente con historial
    history_p001 = get_patient_history("P001")
    assert "Historial del Paciente P001" in history_p001
    assert "Metformina" in history_p001

    # Paciente sin historial o con mensaje específico
    history_p004 = get_patient_history("P004")
    assert "No hay sesiones anteriores" in history_p004

    # Paciente desconocido
    history_unknown = get_patient_history("PX99")
    assert "No hay sesiones anteriores" in history_unknown


def test_compare_with_previous_sessions():
    # Paciente con comparación
    compare_p002 = compare_with_previous_sessions("P002")
    assert "Comparación Longitudinal P002" in compare_p002
    assert "HbA1c en aumento" in compare_p002

    # Paciente sin comparación
    compare_p004 = compare_with_previous_sessions("P004")
    assert "No se puede realizar una comparación longitudinal" in compare_p004


def test_search_clinical_guidelines():
    # Búsqueda sobre HbA1c
    rag_hba1c = search_clinical_guidelines("¿Cuál es el objetivo de hba1c?")
    assert "ADA Guidelines (HbA1c Target)" in rag_hba1c
    assert "< 7.0%" in rag_hba1c

    # Búsqueda sobre hipoglucemia
    rag_hypo = search_clinical_guidelines("¿Qué hacer con una glucosa de 55?")
    assert "ADA Guidelines (Hypoglycemia)" in rag_hypo
    assert "Nivel 1 de hipoglucemia" in rag_hypo

    # Búsqueda sobre presión arterial
    rag_bp = search_clinical_guidelines("presion arterial recomendada")
    assert "ADA Guidelines (Blood Pressure)" in rag_bp
    assert "< 130/80 mmHg" in rag_bp

    # Búsqueda por defecto
    rag_default = search_clinical_guidelines("ejercicio y dieta")
    assert "ADA Guidelines (General Pharmacologic Therapy)" in rag_default
