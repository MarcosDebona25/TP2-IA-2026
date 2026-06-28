# tests/test_monitor_tools.py
#
# Tests determinísticos de las tools del Monitor sobre el fixture data/sample/. Ver
# docs/tests.md (qué cubre cada archivo y por qué).
#
# Estructura (contrato A+C, ver "Flujo de métricas" en docs/CLAUDE.md):
#   - Núcleos puros (_compute_stats, _detect_violations) → se testean con listas literales.
#   - Ventaneo (window_metrics) + TimeRange → recorte temporal en un solo lugar.
#   - Wrappers (calculate_stats, detect_threshold_violations) → por patient_id + timerange.

from datetime import date

import pytest

from orchestrator.state import Alert, Medication, MetricStats, PatientMetrics, TimeRange
from tools.patient_tools import (
    _compute_stats,
    calculate_stats,
    get_medication_schedule,
    get_metric_series,
    load_patient_data,
    window_metrics,
)
from tools.threshold_tools import (
    ADA_THRESHOLDS,
    _detect_violations,
    detect_threshold_violations,
)


# -------------------------------------------------------------------
# load_patient_data
# -------------------------------------------------------------------

def test_load_patient_data_controlado():
    pm = load_patient_data("P001")
    assert isinstance(pm, PatientMetrics)
    assert len(pm.dates) == 12
    assert len({
        len(pm.dates), len(pm.glucose_fasting), len(pm.hba1c),
        len(pm.glucose_postprandial), len(pm.weight),
        len(pm.blood_pressure_systolic), len(pm.blood_pressure_diastolic),
    }) == 1
    assert pm.dates[0] == date(2025, 1, 15)
    assert pm.dates[-1] == date(2025, 12, 15)


def test_load_patient_data_ordena_por_fecha():
    pm = load_patient_data("P002")
    assert pm.dates == sorted(pm.dates)


def test_load_patient_data_datos_insuficientes_una_fila():
    pm = load_patient_data("P004")
    assert len(pm.dates) == 1
    assert pm.hba1c == [6.5]


def test_load_patient_data_paciente_inexistente():
    with pytest.raises(FileNotFoundError):
        load_patient_data("NO_EXISTE")


# -------------------------------------------------------------------
# TimeRange (validación del contrato)
# -------------------------------------------------------------------

def test_timerange_global_por_defecto():
    assert TimeRange().is_global is True


def test_timerange_no_permite_meses_y_fechas_juntos():
    with pytest.raises(ValueError):
        TimeRange(last_n_months=3, start=date(2025, 1, 1))


def test_timerange_meses_debe_ser_positivo():
    with pytest.raises(ValueError):
        TimeRange(last_n_months=0)


def test_timerange_start_posterior_a_end_falla():
    with pytest.raises(ValueError):
        TimeRange(start=date(2025, 6, 1), end=date(2025, 1, 1))


# -------------------------------------------------------------------
# window_metrics (ventaneo único)
# -------------------------------------------------------------------

def test_window_global_devuelve_serie_completa():
    pm = load_patient_data("P002")
    assert window_metrics(pm, None) is pm
    assert len(window_metrics(pm, TimeRange()).dates) == 12


def test_window_ultimos_n_meses():
    pm = load_patient_data("P002")
    w = window_metrics(pm, TimeRange(last_n_months=3))
    assert len(w.dates) == 3
    assert w.dates == pm.dates[-3:]
    assert w.hba1c == pm.hba1c[-3:]


def test_window_n_meses_mayor_que_serie_no_rompe():
    pm = load_patient_data("P004")  # 1 fila
    w = window_metrics(pm, TimeRange(last_n_months=6))
    assert len(w.dates) == 1


def test_window_rango_de_fechas_inclusive():
    pm = load_patient_data("P002")
    w = window_metrics(pm, TimeRange(start=date(2025, 10, 15), end=date(2025, 12, 15)))
    assert w.dates == [date(2025, 10, 15), date(2025, 11, 15), date(2025, 12, 15)]


def test_window_preserva_alineacion_de_series():
    pm = load_patient_data("P003")
    w = window_metrics(pm, TimeRange(last_n_months=4))
    # Todas las series quedan con el mismo largo tras recortar.
    assert len({len(w.dates), len(w.hba1c), len(w.glucose_fasting), len(w.weight)}) == 1


# -------------------------------------------------------------------
# get_metric_series
# -------------------------------------------------------------------

def test_get_metric_series_metrica_invalida():
    pm = load_patient_data("P001")
    with pytest.raises(ValueError):
        get_metric_series(pm, "colesterol")


# -------------------------------------------------------------------
# _compute_stats (núcleo puro)
# -------------------------------------------------------------------

def test_compute_stats_valores_conocidos():
    stats = _compute_stats([6.0, 6.2, 6.4])
    assert isinstance(stats, MetricStats)
    assert stats.mean == pytest.approx(6.2)
    assert stats.last_value == 6.4
    assert stats.min_value == 6.0
    assert stats.max_value == 6.4
    assert stats.delta == pytest.approx(0.4)
    assert stats.direction == "subiendo"


def test_compute_stats_tendencia_descendente():
    stats = _compute_stats([120.0, 110.0, 100.0])
    assert stats.delta == pytest.approx(-20.0)
    assert stats.direction == "bajando"
    assert stats.min_value == 100.0
    assert stats.max_value == 120.0


def test_compute_stats_estable_dentro_de_banda_muerta():
    # Cambio neto < 3% de la media → "estable" (ruido clínicamente irrelevante).
    stats = _compute_stats([100.0, 101.0, 100.5])
    assert stats.direction == "estable"


def test_compute_stats_min_max_exponen_extremo_oculto():
    # La media esconde el 55, pero min_value lo expone (caso hipoglucemia P003).
    stats = _compute_stats([95.0, 92.0, 55.0, 94.0])
    assert stats.mean > 80.0
    assert stats.min_value == 55.0


def test_compute_stats_un_solo_valor():
    stats = _compute_stats([80.0])
    assert stats.mean == 80.0
    assert stats.last_value == 80.0
    assert stats.min_value == 80.0
    assert stats.max_value == 80.0
    assert stats.delta == 0.0
    assert stats.direction == "estable"


def test_compute_stats_vacio_lanza():
    with pytest.raises(ValueError):
        _compute_stats([])


# -------------------------------------------------------------------
# calculate_stats (wrapper por patient_id + timerange)
# -------------------------------------------------------------------

def test_calculate_stats_global():
    stats = calculate_stats("P002", "hba1c")
    assert stats.last_value == 8.2          # último registro de P002
    assert stats.direction == "subiendo"    # tendencia ascendente
    assert stats.delta == pytest.approx(2.2)  # 8.2 - 6.0


def test_calculate_stats_respeta_timerange():
    full = calculate_stats("P002", "hba1c")
    last3 = calculate_stats("P002", "hba1c", TimeRange(last_n_months=3))
    # La ventana cambia el resultado: la media de los últimos 3 es mayor que la global.
    assert last3.mean > full.mean
    assert last3.last_value == full.last_value == 8.2


def test_calculate_stats_es_deterministica():
    tr = TimeRange(last_n_months=6)
    assert calculate_stats("P003", "glucose_fasting", tr) == calculate_stats("P003", "glucose_fasting", tr)


def test_calculate_stats_metrica_invalida():
    with pytest.raises(ValueError):
        calculate_stats("P001", "colesterol")


# -------------------------------------------------------------------
# _detect_violations (núcleo puro)
# -------------------------------------------------------------------

def test_detect_severidades_moderada_y_severa():
    fechas = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)]
    # 90 normal (<100), 110 moderada (100-125), 130 severa (>=126).
    alerts = _detect_violations("glucose_fasting", [90.0, 110.0, 130.0], fechas)
    assert [a.severity for a in alerts] == ["moderada", "severa"]
    assert all(isinstance(a, Alert) for a in alerts)
    assert alerts[0].value == 110.0
    assert alerts[0].date == date(2025, 2, 1)


def test_detect_metrica_sin_umbral_devuelve_vacio():
    assert _detect_violations("weight", [120.0], [date(2025, 1, 1)]) == []


def test_detect_largos_desalineados_lanza():
    with pytest.raises(ValueError):
        _detect_violations("hba1c", [6.0, 6.5], [date(2025, 1, 1)])


def test_detect_limites_exactos_ada():
    f = [date(2025, 1, 1)]
    assert _detect_violations("hba1c", [ADA_THRESHOLDS["hba1c"]["high"]["alerta"]], f)[0].severity == "moderada"
    assert _detect_violations("hba1c", [ADA_THRESHOLDS["hba1c"]["high"]["critico"]], f)[0].severity == "severa"


def test_detect_hipoglucemia_moderada_y_severa():
    f = [date(2025, 1, 1), date(2025, 2, 1)]
    # 60 mg/dL → hipo moderada (< 70); 50 mg/dL → hipo severa (< 54).
    alerts = _detect_violations("glucose_fasting", [60.0, 50.0], f)
    assert [a.severity for a in alerts] == ["moderada", "severa"]
    assert "hipoglucemia" in alerts[0].description


def test_detect_hba1c_no_tiene_banda_baja():
    # HbA1c baja no es alerta (no hay banda 'low' definida).
    assert _detect_violations("hba1c", [4.0], [date(2025, 1, 1)]) == []


# -------------------------------------------------------------------
# detect_threshold_violations (wrapper por patient_id + timerange)
# -------------------------------------------------------------------

def test_threshold_controlado_sin_alertas():
    assert detect_threshold_violations("P001", "glucose_fasting") == []


def test_threshold_tendencia_ascendente_tiene_severas():
    alerts = detect_threshold_violations("P002", "hba1c")
    assert "severa" in {a.severity for a in alerts}   # P002 llega a HbA1c >= 6.5


def test_threshold_metrica_sin_umbral_devuelve_vacio():
    assert detect_threshold_violations("P002", "weight") == []


def test_threshold_detecta_hipoglucemia_de_p003():
    # P003 tiene un episodio de 55 mg/dL en ayunas: antes era invisible, ahora se detecta.
    alerts = detect_threshold_violations("P003", "glucose_fasting")
    assert len(alerts) == 1
    assert alerts[0].value == 55.0
    assert alerts[0].severity == "moderada"
    assert "hipoglucemia" in alerts[0].description


def test_threshold_respeta_timerange():
    # Primeros meses de P002 con HbA1c < 6.5 (solo moderadas); la ventana los aísla.
    alerts = detect_threshold_violations("P002", "hba1c", TimeRange(start=date(2025, 1, 15), end=date(2025, 3, 15)))
    assert {a.severity for a in alerts} == {"moderada"}


# -------------------------------------------------------------------
# get_medication_schedule
# -------------------------------------------------------------------

def test_get_medication_schedule_devuelve_modelos():
    meds = get_medication_schedule("P002")
    assert len(meds) == 2
    assert all(isinstance(m, Medication) for m in meds)
    assert meds[0].name == "Metformina"
    assert meds[0].dose == "1000mg"


def test_get_medication_schedule_paciente_sin_meds():
    assert get_medication_schedule("NO_EXISTE") == []
