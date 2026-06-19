# tools/rag_tools.py
#
# Stub de búsqueda RAG en guías clínicas de la ADA (contrato provisional con B).
# Cuando B entregue, esta herramienta realizará búsquedas vectoriales sobre ChromaDB.

def search_clinical_guidelines(query: str) -> str:
    """Busca fragmentos relevantes de las guías clínicas de la ADA basados en el query.

    Retorna extractos en lenguaje natural que fundamentan las decisiones clínicas.
    """
    q = query.lower()
    
    if "hba1c" in q or "aumento" in q or "hemoglobina" in q:
        return (
            "ADA Guidelines (HbA1c Target):\n"
            "- El objetivo general de HbA1c para adultos con diabetes tipo 2 no embarazados es < 7.0% (53 mmol/mol).\n"
            "- Objetivos menos estrictos (< 8.0%) pueden ser adecuados para pacientes con historial de hipoglucemia severa, expectativa de vida limitada o complicaciones avanzadas.\n"
            "- Si no se alcanza el objetivo tras 3 meses de monoterapia (Metformina), se debe intensificar con terapia dual agregando un segundo agente (SGLT2i, GLP-1 RA, DPP-4i, etc.) considerando comorbilidades cardiovasculares o renales."
        )
    
    if "hipo" in q or "bajo" in q or "55" in q or "glucosa en ayunas" in q and "ayuna" in q:
        # Si menciona hipoglucemia o valores bajos
        if "hipo" in q or "bajo" in q or "55" in q:
            return (
                "ADA Guidelines (Hypoglycemia):\n"
                "- Nivel 1 de hipoglucemia: Glucosa < 70 mg/dL (pero >= 54 mg/dL). Nivel 2 de hipoglucemia: Glucosa < 54 mg/dL.\n"
                "- En cada consulta médica se debe indagar sobre la frecuencia, severidad y causas de los episodios de hipoglucemia.\n"
                "- Si el paciente experimenta hipoglucemia clínica o no percibida (especialmente Nivel 2 o 3), se debe reevaluar el tratamiento para disminuir el riesgo de nuevos eventos, ajustando dosis de secretagogos o insulinas si están presentes."
            )
            
    if "presion" in q or "presión" in q or "hipertension" in q or "hipertensión" in q or "sistolica" in q or "diastolica" in q:
        return (
            "ADA Guidelines (Blood Pressure):\n"
            "- El objetivo de presión arterial recomendado para personas con diabetes es < 130/80 mmHg si se puede lograr de manera segura.\n"
            "- Para pacientes con presión arterial confirmed >= 130/80 mmHg, se debe iniciar tratamiento farmacológico junto con terapia de estilo de vida.\n"
            "- Los fármacos de primera línea son los IECAs (ej. Enalapril) o ARA-II (ej. Losartán), especialmente en presencia de microalbuminuria."
        )
        
    # Default general
    return (
        "ADA Guidelines (General Pharmacologic Therapy):\n"
        "- La Metformina es el tratamiento de primera línea preferido para la diabetes tipo 2, a menos que existan contraindicaciones.\n"
        "- Se debe considerar el inicio temprano de terapia combinada para acortar el tiempo hasta el objetivo glucémico.\n"
        "- El manejo integral debe incluir metas de estilo de vida, control de peso, cese del hábito tabáquico y evaluación del riesgo cardiovascular."
    )
