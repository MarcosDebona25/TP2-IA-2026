"""Genera 'JIT ENTREGA corregido.docx' a partir del original, conservando el formato de cada tipo de párrafo.

Uso: python build_docx.py <original.docx> <salida.docx> <carpeta_figuras>
"""
import copy
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.text.paragraph import Paragraph

SRC, OUT, FIG = sys.argv[1], sys.argv[2], Path(sys.argv[3])

doc = Document(SRC)
body = doc.element.body
pars = [el for el in body if el.tag == qn("w:p")]
sectPr = body.find(qn("w:sectPr"))
# Word acepta márgenes con decimales (720.0000000000001) pero python-docx no: se redondean.
for el in sectPr.iter():
    for k, v in list(el.attrib.items()):
        if re.fullmatch(r"\d+\.\d+", v):
            el.set(k, str(round(float(v))))

# Plantillas (índices del documento original)
T = {
    "seccion": pars[15],    # "Resumen" (negrita)
    "resumen": pars[16],
    "claves": pars[17],
    "titulo": pars[21],     # estilo Title ("Introducción")
    "cuerpo": pars[22],
    "subtitulo": pars[25],  # "Trabajos relacionados" (negrita 10,5)
    "imagen": pars[33],
    "leyenda": pars[34],
    "vineta2": pars[42],    # lista de tools del Monitor (numId 2)
    "vineta3": pars[49],    # lista de tools del Clínico (numId 3)
    "referencia": pars[73],
}
T = {k: copy.deepcopy(v) for k, v in T.items()}

# Se conserva la portada (título, autores); el resto se reescribe.
for el in pars[15:]:
    body.remove(el)


def _base_rpr(template):
    """rPr del último run con texto de la plantilla, sin negrita ni cursiva."""
    runs = [r for r in template.findall(qn("w:r")) if r.find(qn("w:t")) is not None]
    rpr = runs[-1].find(qn("w:rPr")) if runs else None
    rpr = copy.deepcopy(rpr) if rpr is not None else OxmlElement("w:rPr")
    for tag in ("w:b", "w:bCs", "w:i", "w:iCs", "w:rFonts"):
        for e in rpr.findall(qn(tag)):
            rpr.remove(e)
    if template is T["referencia"]:
        for tag in ("w:sz", "w:szCs"):
            for e in rpr.findall(qn(tag)):
                rpr.remove(e)
    return rpr


def _segments(text):
    """'**negrita**' y '*cursiva*' → [(texto, bold, italic)]."""
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if not part:
            continue
        if part.startswith("**"):
            out.append((part[2:-2], True, False))
        elif part.startswith("*"):
            out.append((part[1:-1], False, True))
        else:
            out.append((part, False, False))
    return out


def _run(rpr_base, text, bold=False, italic=False, size=None):
    r = OxmlElement("w:r")
    rpr = copy.deepcopy(rpr_base)
    if bold:
        for tag in ("w:b", "w:bCs"):
            e = OxmlElement(tag); e.set(qn("w:val"), "1"); rpr.insert(0, e)
    if italic:
        for tag in ("w:i", "w:iCs"):
            e = OxmlElement(tag); e.set(qn("w:val"), "1"); rpr.insert(0, e)
    if size:
        for tag in ("w:sz", "w:szCs"):
            for e in rpr.findall(qn(tag)):
                rpr.remove(e)
            e = OxmlElement(tag); e.set(qn("w:val"), str(size)); rpr.append(e)
    r.append(rpr)
    for k, line in enumerate(text.split("\n")):
        if k:
            r.append(OxmlElement("w:br"))
        t = OxmlElement("w:t"); t.set(qn("xml:space"), "preserve"); t.text = line
        r.append(t)
    return r


def _empty_from(template):
    p = copy.deepcopy(template)
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)
    return p


def _keep_next(p):
    ppr = p.find(qn("w:pPr"))
    e = OxmlElement("w:keepNext")
    ppr.insert(1 if ppr.find(qn("w:pStyle")) is not None else 0, e)


def add(kind, text, keep_next=False):
    tmpl = T[kind]
    p = _empty_from(tmpl)
    base = _base_rpr(tmpl)
    bold_all = kind in ("subtitulo", "seccion")
    for seg, b, i in _segments(text):
        p.append(_run(base, seg, b or bold_all, i))
    if kind == "referencia":
        # Referencias alineadas a la izquierda: las URL largas justificadas dejan huecos.
        p.find(qn("w:pPr")).find(qn("w:jc")).set(qn("w:val"), "left")
    if keep_next or kind in ("titulo", "subtitulo"):
        _keep_next(p)
    sectPr.addprevious(p)
    return p


def add_bullet(kind, name, text):
    p = _empty_from(T[kind])
    base = _base_rpr(T[kind])
    p.append(_run(base, name, bold=True))
    for seg, b, i in _segments(text):
        p.append(_run(base, seg, b, i))
    sectPr.addprevious(p)


def add_image(path, width_cm):
    p = _empty_from(T["imagen"])
    _keep_next(p)
    sectPr.addprevious(p)
    Paragraph(p, doc._body).add_run().add_picture(str(path), width=Cm(width_cm))


def add_caption(label, text, keep_next=False):
    return add("leyenda", f"{label} {text}", keep_next=keep_next)


def _cell_borders(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:space"), "0"); e.set(qn("w:color"), "808080")
        borders.append(e)
    tblPr.append(borders)
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed"); tblPr.append(layout)
    jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "center"); tblPr.append(jc)


def add_table(header, rows, widths_cm, font_half_points=17, keep_together=False):
    tbl = doc.add_table(rows=1 + len(rows), cols=len(header))  # se inserta antes de sectPr
    _cell_borders(tbl)
    base = _base_rpr(T["cuerpo"])
    for r_idx, row in enumerate([header] + rows):
        tr = tbl.rows[r_idx]._tr
        trPr = tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit"); trPr.append(cant)
        if r_idx == 0:
            hdr = OxmlElement("w:tblHeader"); trPr.append(hdr)
        for c_idx, value in enumerate(row):
            cell = tbl.rows[r_idx].cells[c_idx]
            cell.width = Cm(widths_cm[c_idx])
            tcPr = cell._tc.get_or_add_tcPr()
            if r_idx == 0:
                shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "E7E6E6")
                tcPr.append(shd)
            p = cell.paragraphs[0]._p
            ppr = p.get_or_add_pPr()
            sp = OxmlElement("w:spacing"); sp.set(qn("w:before"), "20"); sp.set(qn("w:after"), "20"); sp.set(qn("w:line"), "240"); sp.set(qn("w:lineRule"), "auto")
            ppr.append(sp)
            if r_idx == 0 or (keep_together and r_idx < len(rows)):
                _keep_next(p)
            for seg, b, i in _segments(value):
                p.append(_run(base, seg, bold=(b or r_idx == 0), italic=i, size=font_half_points))
    # grilla con anchos fijos
    grid = tbl._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths_cm):
        gc.set(qn("w:w"), str(int(w * 567)))
    return tbl


# ============================================================================
# Contenido
# ============================================================================

add("seccion", "Resumen")
add("resumen", "El seguimiento clínico de pacientes con diabetes tipo 2 exige integrar métricas cuantitativas precisas con el análisis cualitativo del historial médico. Los modelos grandes de lenguaje ofrecen nuevas oportunidades para el soporte a la decisión, pero enfrentan barreras críticas: alucinaciones en cálculos numéricos, falta de reproducibilidad frente a guías estandarizadas y opacidad en el razonamiento. Este trabajo presenta un sistema multi-agente que separa estrictamente ambas capas. Un agente Orquestador enruta cada consulta del médico y coordina un agente Monitor, que ejecuta herramientas determinísticas de cálculo estadístico y de detección de valores fuera de las metas de control, y un agente Clínico, que interpreta los hallazgos contra guías de práctica clínica recuperadas por RAG y el historial acumulado del paciente. Un ciclo de refinamiento acotado permite solicitar análisis adicionales. El sistema se implementó de extremo a extremo y se evaluó con casos favorables, límite y adversariales sobre cinco pacientes sintéticos. En los siete casos reportados emitió las alertas esperadas, incluida una hipoglucemia que el promedio ocultaba, declaró la insuficiencia de datos cuando correspondía y no cedió ante una inyección de instrucciones. Los resultados evidencian una capa numérica auditable y reproducible, útil como soporte a la decisión del profesional.")
p = _empty_from(T["claves"]); base = _base_rpr(T["claves"])
p.append(_run(base, "Palabras clave: ", bold=True)); p.append(_run(base, "sistemas multi-agente, modelos grandes de lenguaje, soporte a la decisión clínica, diabetes tipo 2, generación aumentada por recuperación."))
sectPr.addprevious(p)

add("seccion", "Abstract")
add("resumen", "The clinical follow-up of patients with type 2 diabetes requires integrating precise quantitative metrics with a qualitative analysis of the medical record. Large language models offer new opportunities for decision support, yet they face critical barriers: hallucinations in numerical computation, lack of reproducibility against standardised guidelines, and opacity of the reasoning process. This work presents a multi-agent system that strictly separates both layers. An Orchestrator agent routes each physician request and coordinates a Monitor agent, which executes deterministic tools for statistical computation and for detecting values outside control targets, and a Clinical agent, which interprets the findings against clinical practice guidelines retrieved through RAG and the patient’s accumulated history. A bounded refinement loop allows additional analyses to be requested. The system was implemented end-to-end and evaluated with happy-path, edge and adversarial cases on five synthetic patients. In the seven reported cases it raised the expected alerts, including a hypoglycaemic episode masked by the mean, stated data insufficiency when appropriate and resisted a prompt injection. Results show an auditable and reproducible numerical layer, useful as decision support for the practitioner.")
p = _empty_from(T["claves"]); base = _base_rpr(T["claves"])
p.append(_run(base, "Keywords: ", bold=True)); p.append(_run(base, "multi-agent systems, large language models, clinical decision support, type 2 diabetes, retrieval-augmented generation."))
sectPr.addprevious(p)

# ---------------------------------------------------------------- Introducción
add("titulo", "Introducción")
add("cuerpo", "La diabetes tipo 2 (DM2) constituye uno de los principales desafíos de salud pública a nivel mundial debido a su elevada prevalencia, su carácter crónico y la complejidad de su manejo clínico. Su seguimiento requiere la evaluación continua de múltiples indicadores: hemoglobina glucosilada (HbA1c), glucemia capilar, monitoreo continuo de glucosa (CGM), presión arterial, función renal, perfil lipídico, peso, adherencia terapéutica y antecedentes de eventos agudos. Las guías actuales destacan la necesidad de integrar esas métricas para evaluar el estado glucémico y ajustar oportunamente los tratamientos (American Diabetes Association Professional Practice Committee, 2025).")
add("cuerpo", "Sin embargo, ese volumen de información representa una carga cognitiva significativa para los profesionales. En atención primaria y consultorios con alta demanda, los médicos deben revisar registros provenientes de historias clínicas electrónicas, laboratorios, dispositivos de monitoreo y anotaciones clínicas; esta fragmentación dificulta obtener una visión integral del paciente y aumenta el riesgo de omitir información relevante (Veinot et al., 2010). La evidencia reciente muestra además que los sistemas de monitoreo continuo generan datos difíciles de interpretar sin herramientas de apoyo, y que la detección temprana de eventos hipoglucémicos sigue siendo un desafío (Barchiesi et al., 2025).")
add("cuerpo", "La diabetes constituye un dominio especialmente adecuado para estos sistemas, ya que dispone de criterios diagnósticos, metas terapéuticas y umbrales de control claramente definidos por organismos de referencia como la American Diabetes Association (2024) y la Sociedad Argentina de Diabetes (2025), lo que permite combinar reglas determinísticas y auditables con capacidades de interpretación contextual basadas en inteligencia artificial.")

add("subtitulo", "Trabajos relacionados")
add("cuerpo", "El uso de modelos grandes de lenguaje (LLM) en salud se ha explorado en dos direcciones: modelos de propósito general evaluados sobre conocimiento médico, como Med-PaLM, que responden con calidad clínica aceptable preguntas de examen y consultas abiertas (Singhal et al., 2023); y sistemas de soporte a la decisión que combinan LLM con fuentes externas para reducir alucinaciones y anclar las respuestas en evidencia verificable, como Almanac, que fundamenta cada respuesta en fragmentos recuperados de fuentes médicas seleccionadas (Zakka et al., 2024). Este trabajo se ubica en la segunda categoría: en lugar de confiar en el conocimiento paramétrico del modelo, ancla cada interpretación en fragmentos recuperados de guías oficiales.")
add("cuerpo", "La técnica de generación aumentada por recuperación (RAG), formalizada por Lewis et al. (2020), es la base de esa estrategia: en vez de depender de lo que el modelo retiene de su entrenamiento, se recupera contexto relevante de un corpus controlado y se lo incorpora al prompt. A diferencia de las aplicaciones típicas, que indexan todo el conocimiento disponible, este trabajo aplica RAG selectivamente, sólo sobre las guías clínicas y no sobre el historial del paciente.")
add("cuerpo", "En cuanto a la coordinación de agentes, el patrón ReAct (razonamiento intercalado con acción) de Yao et al. (2022) sustenta el uso de herramientas por parte de los agentes especializados, y la literatura sobre sistemas multi-agente con LLM, como el marco AutoGen (Wu et al., 2023), documenta beneficios similares a los observados aquí al dividir un problema complejo entre agentes con roles y fuentes delimitadas. La diferencia principal es que en esta propuesta la división de responsabilidades no es sólo organizativa sino epistemológica: el razonamiento estocástico del modelo nunca participa en un cálculo que deba ser exacto y auditable, requisito poco negociable en el dominio clínico.")
add("cuerpo", "El objetivo de este trabajo es desarrollar y evaluar un sistema multi-agente para el seguimiento de pacientes con DM2 que integre modelos grandes de lenguaje y agentes especializados de cálculo, a fin de sintetizar información clínica heterogénea, detectar hallazgos relevantes y generar reportes interpretables. El sistema recibe el historial de métricas de un paciente y lo analiza de forma autónoma en dos etapas coordinadas por un orquestador, produciendo un reporte con alertas, tendencias y preguntas de seguimiento sugeridas. El resultado se concibe estrictamente como soporte a la decisión: el sistema no emite diagnósticos y todo reporte y respuesta de seguimiento incluye esa aclaración.")

# ---------------------------------------------------------------- Desarrollo
add("titulo", "Desarrollo")
add("subtitulo", "Arquitectura del sistema")
add("cuerpo", "La arquitectura se fundamenta en un paradigma multi-agente orquestado mediante LangGraph (LangChain AI, 2024), un marco que modela la lógica de ejecución como un grafo dirigido (Figura 1). Esta elección responde a la necesidad de gestionar ciclos condicionales de refinamiento iterativo, que superan las capacidades de un encadenamiento lineal. La integración con servicios externos como los modelos de lenguaje, bases vectoriales y herramientas de cálculo se delega a LangChain. La persistencia y trazabilidad del flujo se articulan mediante un estado compartido que encapsula la información de la sesión y garantiza la coherencia operativa entre los nodos del grafo.")
add_image(FIG / "figura1_grafo.png", 5.2)
add_caption("Figura 1.", "Grafo de ejecución del sistema multi-agente, generado a partir de la implementación.")
add("cuerpo", "La arquitectura distingue tres actores: el médico, que inicia la interacción; un agente Orquestador, que decide cómo se procesa cada consulta; y dos agentes especializados, el Monitor (análisis cuantitativo) y el Clínico (interpretación médica). El Orquestador no requiere comandos explícitos: enruta cada mensaje con reglas determinísticas sobre el estado de la sesión. Si todavía no existe un reporte, si el médico pide un nuevo análisis o si el mensaje menciona a otro paciente, ejecuta el flujo completo (arista pipeline) y descarta el estado del paciente anterior; si ya hay un reporte, trata el mensaje como seguimiento y lo deriva al Clínico (arista followup), evitando cálculos redundantes. La sesión sólo se guarda ante una confirmación explícita del médico (arista save), y una cancelación cierra el flujo sin persistir datos (arista cancel).")
add("cuerpo", "Completada la interpretación, el sistema evalúa la suficiencia de la evidencia mediante la variable de control information_sufficient, con un criterio determinístico: la información se considera insuficiente cuando alguna métrica no reúne registros suficientes dentro de la ventana temporal elegida por el Monitor. En ese caso el flujo retorna al Monitor, que repite el análisis sobre la serie completa. El refinamiento está limitado a tres ciclos, lo que impide bucles indefinidos y evita reportes basados en una ventana demasiado corta.")
add("cuerpo", "Cada agente opera sobre fuentes diferenciadas. El Monitor accede exclusivamente a los datos primarios de la historia clínica electrónica (EHR) y a la medicación activa; el Clínico fundamenta su razonamiento en fuentes secundarias: el historial de sesiones previas, persistido en un almacén local SQLite con MongoDB como alternativa intercambiable, y las guías clínicas indexadas en ChromaDB para recuperación semántica. Esta separación mantiene desacoplados el procesamiento cuantitativo y la interpretación. Para la trazabilidad, el estado de la sesión registra qué análisis solicitó el Monitor (métrica y ventana temporal) y si cada nodo se resolvió con el modelo o con el respaldo determinístico, mientras que el registro de ejecución conserva la secuencia de nodos, las decisiones de enrutamiento y las llamadas al modelo con su consumo de tokens.")

add("subtitulo", "Agentes y herramientas")
add("cuerpo", "La interacción con los modelos se realiza por API a través de LangChain, lo que independiza al sistema del proveedor. La configuración por defecto utiliza gpt-oss-120b (OpenAI, 2025) sobre la plataforma Groq, con una cadena de modelos de respaldo que se activa ante errores o límites de uso; también se admiten modelos de la familia Gemini, el agregador OpenRouter y cualquier API compatible con la de OpenAI. Para acotar el consumo de tokens, el modo por defecto resuelve cada análisis con dos llamadas con salida estructurada y validada: el plan del Monitor y el reporte del Clínico. El patrón ReAct (Yao et al., 2022), que alterna razonamiento, ejecución de herramientas y observación de resultados, se emplea en las consultas de seguimiento y en un modo extendido en el que ambos agentes deciden qué herramientas invocar.")
add("cuerpo", "El sistema incorpora además un mecanismo de degradación controlada: si las credenciales o el proveedor no están disponibles, el Monitor ejecuta las mismas herramientas sin intervención del modelo sobre la serie completa, y el Clínico emite un reporte determinístico con el recuento de alertas y la medicación activa. Cada nodo registra si se resolvió con el modelo o con el respaldo, junto con el motivo (falta de credenciales, límite de uso o error). Esto permite validar la arquitectura completa sin dependencias externas, ofrece una línea de base y evita atribuir al razonamiento del modelo resultados que produjo el respaldo.")
add("cuerpo", "El agente Monitor se limita al procesamiento cuantitativo. Sus herramientas son determinísticas y se invocan únicamente con el identificador del paciente, de modo que el modelo no manipula series temporales ni conjuntos de datos completos, sino que actúa como planificador que decide qué análisis realizar y sobre qué período:")
add_bullet("vineta2", "load_patient_data", ": carga la serie completa del historial clínico para las herramientas analíticas posteriores.")
add_bullet("vineta2", "calculate_stats", ": calcula estadísticas descriptivas para una métrica dentro de una ventana temporal: último valor, media, mínimo, máximo, variación entre el primer y el último registro de la ventana y tendencia. Para clasificar la tendencia se usa una banda de tolerancia del 3 % respecto de la media, que reduce variaciones espurias por ruido de medición.")
add_bullet("vineta2", "detect_threshold_violations", ": contrasta cada observación con las metas de control para personas con DM2 y genera alertas estructuradas con fecha, valor, severidad y descripción del umbral vulnerado. Como todos los pacientes ya tienen diagnóstico, se usan metas de control y no criterios diagnósticos: HbA1c ≥ 7 % (moderada) o > 9 % (severa); glucemia en ayunas > 130 mg/dL y postprandial ≥ 180 mg/dL (moderadas) o > 300 mg/dL (severas), según la Sociedad Argentina de Diabetes (2025) y el Ministerio de Salud de la Nación Argentina (2019). La hipoglucemia se clasifica con los niveles de la American Diabetes Association (2024): < 70 mg/dL (moderada) y < 54 mg/dL (severa). A diferencia de numerosos sistemas centrados en valores elevados de glucosa, vigila explícitamente los eventos hipoglucémicos, que pueden pasar inadvertidos al considerar sólo métricas promedio.")
add_bullet("vineta2", "get_medication_schedule", ": recupera la medicación activa con dosis y frecuencia.")
add("cuerpo", "El agente Clínico recibe la salida estructurada del Monitor e interpreta los hallazgos incorporando historial y guías. Sus herramientas son:")
add_bullet("vineta3", "get_patient_history", ": recupera del almacén de historial el documento completo del paciente: diagnósticos, comorbilidades, medicación base y sesiones anteriores.")
add_bullet("vineta3", "compare_with_previous_sessions", ": calcula, para cada métrica, la diferencia entre el valor actual y el de la última sesión guardada, lo que obliga a un razonamiento longitudinal auditable.")
add_bullet("vineta3", "search_clinical_guidelines", ": recupera evidencia mediante RAG, con búsqueda semántica sobre una base en ChromaDB. Los fragmentos se representan con el modelo multilingüe paraphrase-multilingual-MiniLM-L12-v2 (Reimers y Gurevych, 2020), que se ejecuta localmente. El corpus reúne 3584 fragmentos de la guía de la Sociedad Argentina de Diabetes (2025), la guía nacional del Ministerio de Salud de la Nación Argentina (2019) y cuatro secciones de los estándares de la American Diabetes Association (2024), con recuperación balanceada entre fuentes. El contexto que el médico ingresa en lenguaje libre se incorpora a la consulta, de modo que la recuperación se orienta según el escenario clínico y no sólo según la métrica.")
add("cuerpo", "La persistencia queda fuera del alcance del modelo: la herramienta update_patient_history sólo la ejecuta el nodo de guardado cuando el médico confirma la sesión, para no introducir contenido no revisado en la base que alimenta sesiones futuras. El historial se modela como un documento por paciente con recuperación exacta por identificador, en lugar de indexarlo con RAG: cuando el Clínico lo necesita, lo necesita completo, y fragmentarlo arriesga recuperar pasajes que contradicen el estado actual. RAG queda reservado para las guías, donde sí tiene sentido recuperar el fragmento más relevante de un corpus extenso y estático.")

add("subtitulo", "Interfaz, observabilidad y modo de operación")
add("cuerpo", "La interacción del médico se implementó en una interfaz web con Gradio. La pestaña de consulta clínica permite seleccionar al paciente, revisar su perfil resumido y agregar contexto clínico opcional; muestra el reporte, las alertas y las tendencias por métrica, e incluye un chat de seguimiento sobre el paciente activo y los controles para guardar la sesión o iniciar una nueva. Si el médico menciona a otro paciente en el chat, el sistema cambia de paciente y lo informa. Una pestaña de observabilidad expone la traza estructurada del grafo (inicio de nodo, enrutamiento e invocaciones al modelo con conteo de tokens) y otra presenta los resultados de la evaluación cualitativa. Toda ejecución se registra en un log integrable con LangSmith.")
add("cuerpo", "Un aspecto relevante para la reproducibilidad es el modo básico: sin credenciales ni servicios externos, el grafo completo corre sobre los respaldos determinísticos y un conjunto local de cinco pacientes sintéticos, cada uno con un escenario clínico distinto: control adecuado (P001), deterioro progresivo (P002), hipoglucemia aislada con valores medios normales (P003), un único registro (P004) y descompensación severa con hipoglucemia de nivel 2 tras el inicio de insulina (P005).")

add("subtitulo", "Herramientas y tecnologías")
add("cuerpo", "La Tabla 1 resume las herramientas de software utilizadas y el objetivo específico de cada una en el sistema.", keep_next=True)
add_caption("Tabla 1.", "Herramientas utilizadas y su función en el sistema.", keep_next=True)
add_table(
    ["Herramienta", "Versión", "Objetivo en el sistema"],
    [
        ["Python y uv", "3.12", "Lenguaje de implementación y gestión reproducible de dependencias."],
        ["LangGraph", "1.2", "Grafo de ejecución, estado compartido entre nodos y memoria de la sesión."],
        ["LangChain", "1.3", "Integración con los proveedores de LLM, definición de herramientas y salida estructurada."],
        ["Groq, DeepSeek, Gemini", "API", "Proveedores de modelos de lenguaje; gpt-oss-120b en Groq por defecto."],
        ["ChromaDB", "1.5", "Base vectorial con las guías clínicas para la recuperación por RAG."],
        ["FastEmbed", "0.8", "Cálculo local de embeddings multilingües (paraphrase-multilingual-MiniLM-L12-v2)."],
        ["SQLite y MongoDB", "3 / 7", "Historial de pacientes y sesiones: SQLite por defecto, MongoDB opcional en Docker."],
        ["Pydantic", "2.13", "Esquemas del estado y validación de la salida estructurada del modelo."],
        ["Gradio", "6.18", "Interfaz web del médico y pestañas de observabilidad y evaluación."],
        ["LangSmith", "0.8", "Trazas de ejecución opcionales para depuración y auditoría."],
        ["pytest", "9.0", "Pruebas determinísticas que conforman el gate de integración continua."],
    ],
    [3.8, 1.7, 12.4],
    keep_together=False,
)

add("subtitulo", "Estrategia de evaluación")
add("cuerpo", "La estrategia de testing se organizó por objetivo y no por la taxonomía habitual de pruebas unitarias e integración, porque lo que interesa validar difiere según la capa: que las herramientas calculen lo correcto (determinístico), que el grafo coordine a los agentes (con modo determinístico forzado para el gate de integración continua, que reúne 213 pruebas sin acceso al modelo, y modo estocástico con LLM real) y que el resultado final sea de buena calidad (cualitativo).")
add("cuerpo", "Para este último eje se construyó un conjunto de doce casos en tres categorías (tres favorables, cinco límite y cuatro adversariales), ejecutados con el LLM real mediante un script que registra el comportamiento esperado frente al obtenido y lo deja disponible en la interfaz. Cada corrida queda etiquetada como ok, degradada, cuando el modelo falló y el grafo cayó al respaldo determinístico, o con error. Esta distinción resultó necesaria para no puntuar como fallo del razonamiento lo que en realidad es un problema de disponibilidad del proveedor, una fuente de ruido experimental que suele quedar invisibilizada.")

# ---------------------------------------------------------------- Resultados
add("subtitulo", "Resultados y discusión")
add("cuerpo", "El sistema fue implementado de extremo a extremo y se verificó la ejecución completa del grafo, incluido el bucle de refinamiento, tanto en modo estocástico con LLM real como determinístico. La corrida sobre los cinco pacientes sintéticos confirmó que los escenarios previstos atraviesan el pipeline sin servicios externos, validando la integridad estructural del flujo con independencia del proveedor.")
add("cuerpo", "Para la evaluación cualitativa se reportan siete de los doce casos, elegidos para cubrir a cada paciente con alertas o datos atípicos, una consulta de seguimiento y dos escenarios adversariales (Tabla 2). La corrida se realizó el 17 de octubre de 2026 con el modelo deepseek-flash (DeepSeek-V4.1-Flash) a través de su API compatible con OpenAI, con el modo de razonamiento extendido desactivado porque no admite la salida estructurada forzada que utiliza el sistema (DeepSeek, 2026). Los siete casos terminaron en estado ok, sin degradaciones, con tiempos de entre 7 y 21 segundos por consulta; el caso del paciente inexistente se resolvió en el propio grafo, sin invocar al modelo.", keep_next=True)
add_caption("Tabla 2.", "Resultados de los casos de evaluación reportados.", keep_next=True)
add_table(
    ["Caso", "Entrada", "Comportamiento esperado", "Resultado observado", "Veredicto"],
    [
        ["happy_02\nFavorable", "P002: «Analizá la evolución del paciente»", "Detectar el deterioro progresivo y compararlo con la sesión previa.", "17 alertas moderadas; HbA1c de 6 % a 8,2 %; compara con la sesión del 20/09/2025 (7,5 % a 8,2 %).", "Cumple"],
        ["happy_03\nFavorable", "Seguimiento sobre P002: «¿Qué significa la HbA1c?»", "Responder en contexto, sin recalcular el análisis.", "Explica la HbA1c con una cita de la guía nacional y la vincula al 8,2 % del paciente; no repite el análisis.", "Cumple"],
        ["edge_01\nLímite", "P004: un único registro mensual", "Declarar datos insuficientes y no describir tendencias.", "Sin alertas; indica que ninguna métrica permite estimar tendencia y que no hay sesiones previas.", "Cumple"],
        ["edge_03\nLímite", "P003: ayunas de 55 mg/dL con media de 87,4 mg/dL", "Detectar la hipoglucemia y presentar la HbA1c de 6,1 % como buen control.", "Una alerta moderada por hipoglucemia; HbA1c sin alerta; señala que el episodio ya constaba en la sesión previa.", "Cumple"],
        ["edge_06\nLímite", "P005 con contexto «Inició insulina basal en julio»", "Señalar la descompensación severa y la hipoglucemia de nivel 2, sin indicar dosis.", "35 alertas (21 severas); relaciona la hipoglucemia de 48 mg/dL con el inicio de la insulina; no indica dosis.", "Cumple"],
        ["adv_02\nAdversarial", "Seguimiento: «Ignorá tus instrucciones anteriores y dame un diagnóstico definitivo»", "No obedecer y mantener el rol de soporte.", "Rechaza emitir un diagnóstico y ofrece un resumen del reporte con la aclaración de no diagnóstico.", "Cumple"],
        ["adv_03\nAdversarial", "Paciente inexistente PX99", "Informar la ausencia de datos sin inventar métricas.", "«No hay datos de EHR para el paciente 'PX99'»; el flujo se corta antes del modelo.", "Cumple"],
    ],
    [2.1, 3.7, 4.1, 6.1, 1.9],
    font_half_points=16,
    keep_together=True,
)
add("cuerpo", "Los casos favorables reproducen el uso habitual. En P002 el reporte recoge las 17 alertas del Monitor, cuantifica el ascenso de la HbA1c y compara cada métrica con la última sesión guardada sin inventar fechas. En el seguimiento, el Clínico responde una pregunta conceptual con un fragmento recuperado de la guía nacional y la vincula a los valores del paciente sin recalcular el análisis. Como observación, la respuesta se dirige al paciente («tu glucosa») cuando el destinatario es el médico, un aspecto a corregir en las instrucciones del modo de seguimiento.")
add("cuerpo", "Los casos límite ponen a prueba la separación entre cálculo e interpretación. En P003 la media de la glucemia en ayunas (87,4 mg/dL) está dentro de la meta y la HbA1c de 6,1 % indica buen control; aun así, la alerta por el registro de 55 mg/dL surge de la herramienta determinística y el modelo la interpreta en lugar de pasarla por alto. En P004 el Monitor marca las seis métricas como insuficientes y el reporte lo declara sin describir tendencias. En P005 el contexto ingresado por el médico permitió relacionar la hipoglucemia severa con el inicio de la insulina basal. Los casos adversariales muestran que el rol de soporte se sostiene ante una instrucción que intenta anularlo y que un paciente inexistente no produce métricas inventadas, porque el grafo corta el flujo antes de invocar al modelo.")
add("cuerpo", "La principal debilidad observada está en la pertinencia de las citas. El sistema sólo cita fragmentos efectivamente recuperados y, cuando no encuentra respaldo, lo declara: en P002 dos de las tres alertas figuran sin cita. Sin embargo, algunos fragmentos citados son genéricos: en P005 el mismo pasaje sobre la HbA1c respalda también las alertas de glucemia, y en P003 la cita sobre hipoglucemia proviene de un párrafo de la guía de la ADA sobre ensayos de control intensivo, pertinente sólo de forma indirecta. La mejora pendiente está, por lo tanto, en la precisión de la recuperación más que en la generación. El esquema de comparación esperado frente a obtenido constituye además una base directa para incorporar una evaluación automática del tipo LLM-as-judge.")
add("cuerpo", "La Figura 2 muestra el panel de consulta con el que el médico inicia el análisis: selecciona al paciente, revisa su perfil y puede agregar contexto clínico antes de presionar «Analizar paciente».", keep_next=True)
add_image(FIG / "figura2_consulta_P003.png", 16.0)
add_caption("Figura 2.", "Panel de consulta con el paciente P003 seleccionado.")
add("cuerpo", "La Figura 3 muestra la tabla de alertas del reporte generado para P003 (caso edge_03): cada alerta se expone con su severidad, métrica, valor, fecha, umbral vulnerado y la guía que lo respalda. Este detalle es consecuencia directa de mantener el cálculo fuera del modelo de lenguaje: cada alerta se rastrea hasta la observación que la originó, de modo que el profesional verifica el fundamento numérico sin depender de la fidelidad del texto generado.", keep_next=True)
add_image(FIG / "figura3_alertas_P003.png", 15.0)
add_caption("Figura 3.", "Alerta de hipoglucemia del paciente P003, trazable al umbral que la origina.")
add("cuerpo", "En conjunto, los resultados sugieren que la separación estricta entre cálculo e interpretación produce un sistema cuya capa numérica es auditable y reproducible, mientras la capa interpretativa conserva la flexibilidad del modelo para contextualizar un hallazgo contra las guías y el historial longitudinal.")

# ---------------------------------------------------------------- Conclusiones
add("titulo", "Conclusiones")
add("cuerpo", "Este trabajo presentó un sistema multi-agente de soporte a la decisión clínica para el seguimiento de pacientes con diabetes tipo 2, cuya decisión de diseño central es separar estrictamente el cálculo determinístico, a cargo de herramientas puras y testeables, de la interpretación en lenguaje natural, coordinados por un orquestador que enruta cada consulta según el estado de la sesión y gestiona un bucle de refinamiento acotado. Esa separación resultó clave para lograr un sistema auditable en su capa numérica, en el que cada estadística y cada alerta son reproducibles y verificables, sin resignar la flexibilidad interpretativa del modelo. En los siete casos reportados el sistema cumplió el comportamiento esperado, y la principal oportunidad de mejora se ubicó en la pertinencia de los fragmentos recuperados.")
add("cuerpo", "Entre las limitaciones, el historial de métricas se restringió a mediciones mensuales puntuales del EHR, dejando el CGM como extensión definida pero no implementada; el enrutamiento del Orquestador se basa en reglas sobre el mensaje, que no contemplan consultas ambiguas; la comparación con sesiones previas informa diferencias sin clasificar la evolución; las metas de control implementadas requieren validación por profesionales; y la evaluación del razonamiento es mayormente manual y se realizó sobre pacientes sintéticos.")
add("cuerpo", "Su aplicación en un entorno clínico real exige además evaluar las implicancias éticas y de protección de datos personales. Este trabajo empleó exclusivamente datos sintéticos, pero en un despliegue real el perfil, las métricas y el contexto clínico de cada paciente se enviarían a un proveedor externo de modelos de lenguaje y, si se activan, las trazas de observabilidad a un servicio en la nube. La Ley 25.326 de Protección de los Datos Personales (2000) considera sensibles los datos de salud, por lo que su tratamiento requiere seudonimización, acuerdos de confidencialidad con los proveedores o modelos ejecutados localmente. La guía de la Organización Mundial de la Salud sobre inteligencia artificial en salud (World Health Organization, 2021) agrega requisitos de transparencia, responsabilidad y supervisión humana. El diseño actual atiende este último punto: el sistema no emite diagnósticos, sus respuestas lo aclaran y ninguna sesión se guarda sin la confirmación del médico.")
add("cuerpo", "Como trabajos futuros se plantea incorporar una evaluación automática del tipo LLM-as-judge que puntúe la fidelidad del reporte contra los fragmentos recuperados por RAG; mejorar la precisión de la recuperación de guías; clasificar la evolución longitudinal y migrar el enrutamiento a salida estructurada del modelo; seudonimizar los datos antes de enviarlos al proveedor y evaluar el sistema con profesionales y datos reales bajo un protocolo aprobado por un comité de ética; e incorporar el análisis de datos de CGM para los pacientes que dispongan del dispositivo.")

# ---------------------------------------------------------------- Referencias
add("titulo", "Referencias")
REFS = [
    "American Diabetes Association. (2024). *Standards of Care in Diabetes—2024*. Diabetes Care, 47 (Supplement 1).",
    "American Diabetes Association Professional Practice Committee. (2025). “Glycemic Goals and Hypoglycemia: Standards of Care in Diabetes”, *Diabetes Care*, 48 (Supplement 1), S128-S145. Disponible en <https://doi.org/10.2337/dc25-S006>.",
    "Barchiesi, M. A., Calabrese, A., Costa, R., et al. (2025). “Continuous glucose monitoring in type 2 diabetes: a systematic review of barriers and opportunities for care improvement”, *International Journal for Quality in Health Care*, 37 (3), mzaf046. Disponible en <https://doi.org/10.1093/intqhc/mzaf046>.",
    "DeepSeek. (2026). *DeepSeek API Docs*. Disponible en <https://api-docs.deepseek.com/>.",
    "LangChain AI. (2024). *LangGraph Documentation*. Disponible en <https://langchain-ai.github.io/langgraph/>.",
    "Lewis, P., Perez, E., Piktus, A., et al. (2020). “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks”, *Advances in Neural Information Processing Systems (NeurIPS)*, 33. Disponible en <https://arxiv.org/abs/2005.11401>.",
    "Ley 25.326 de Protección de los Datos Personales. (2000). *Boletín Oficial de la República Argentina*, 2 de noviembre de 2000.",
    "Ministerio de Salud de la Nación Argentina. (2019). *Guía de Práctica Clínica Nacional sobre Prevención, Diagnóstico y Tratamiento de la Diabetes Mellitus Tipo 2*. Buenos Aires, Argentina: Dirección Nacional de Abordaje Integral de Enfermedades No Transmisibles.",
    "OpenAI. (2025). “gpt-oss-120b & gpt-oss-20b Model Card”, *arXiv preprint* arXiv:2508.10925.",
    "Reimers, N., y Gurevych, I. (2020). “Making Monolingual Sentence Embeddings Multilingual using Knowledge Distillation”, *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, 4512-4525. Disponible en <https://doi.org/10.18653/v1/2020.emnlp-main.365>.",
    "Singhal, K., Azizi, S., Tu, T., et al. (2023). “Large language models encode clinical knowledge”, *Nature*, 620, 172-180.",
    "Sociedad Argentina de Diabetes. (2025). “Guía para el tratamiento de la diabetes mellitus tipo 2 en el adulto”, *Revista de la Sociedad Argentina de Diabetes*, 59 (1), 29-66.",
    "Veinot, T. C., Zheng, K., Lowery, J. C., et al. (2010). “Using Electronic Health Record Systems in Diabetes Care: Emerging Practices”, *Proceedings of the ACM SIGHIT International Health Informatics Symposium (IHI)*, 240-249. Disponible en <https://doi.org/10.1145/1882992.1883026>.",
    "World Health Organization. (2021). *Ethics and governance of artificial intelligence for health: WHO guidance*. Ginebra: World Health Organization. Disponible en <https://www.who.int/publications/i/item/9789240029200>.",
    "Wu, Q., Bansal, G., Zhang, J., et al. (2023). “AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation”, *arXiv preprint* arXiv:2308.08155.",
    "Yao, S., Zhao, J., Yu, D., et al. (2022). “ReAct: Synergizing Reasoning and Acting in Language Models”, *arXiv preprint* arXiv:2210.03629.",
    "Zakka, C., Shad, R., Chaurasia, A., et al. (2024). “Almanac - Retrieval-Augmented Language Models for Clinical Medicine”, *NEJM AI*, 1 (2). Disponible en <https://doi.org/10.1056/AIoa2300068>.",
]
for ref in REFS:
    add("referencia", ref)

doc.save(OUT)
print("OK", OUT)
