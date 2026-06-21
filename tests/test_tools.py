# tests/test_tools.py
#
# Tests de integración para las tools reales de MongoDB y RAG.
#
# Requieren infraestructura activa:
#   - MongoDB en localhost:27017 con tp2_diabetes.patients cargada (data/load_mongo.py)
#   - Ollama en localhost:11434 con nomic-embed-text
#   - ChromaDB indexada (rag/ingest.py)
#
# Correr solo en entorno completo:
#   uv run pytest tests/test_tools.py -m integration

import pytest

from tools.mongo_tools import compare_with_previous_sessions, get_patient_history
from rag.retriever import search_clinical_guidelines


@pytest.mark.integration
def test_get_patient_history_con_datos():
    doc = get_patient_history("P001")
    assert isinstance(doc, dict)
    assert doc.get("patient_id") == "P001"


@pytest.mark.integration
def test_get_patient_history_paciente_inexistente():
    with pytest.raises(ValueError, match="no encontrado"):
        get_patient_history("PX99")


@pytest.mark.integration
def test_compare_with_previous_sessions_sin_metricas():
    result = compare_with_previous_sessions("P001")
    assert isinstance(result, dict)
    assert "sessions_count" in result
    assert "previous_session" in result
    assert "deltas" in result


@pytest.mark.integration
def test_compare_with_previous_sessions_con_metricas():
    result = compare_with_previous_sessions("P001", current_metrics={"hba1c": 7.0})
    assert isinstance(result, dict)
    assert "deltas" in result


@pytest.mark.integration
def test_compare_with_previous_sessions_sin_historial():
    result = compare_with_previous_sessions("P004")
    assert result["previous_session"] is None
    assert result["deltas"] == {}
    assert result["sessions_count"] == 0


@pytest.mark.integration
def test_search_clinical_guidelines_retorna_fragmentos():
    fragments = search_clinical_guidelines("objetivo HbA1c diabetes tipo 2", k=3)
    assert isinstance(fragments, list)
    assert len(fragments) > 0
    assert all(isinstance(f, str) for f in fragments)


@pytest.mark.integration
def test_search_clinical_guidelines_hipoglucemia():
    fragments = search_clinical_guidelines("manejo hipoglucemia nivel 1", k=2)
    assert isinstance(fragments, list)
    assert len(fragments) > 0
