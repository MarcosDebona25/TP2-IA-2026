# SISTEMA MULTI-AGENTE DE SOPORTE CLÍNICO PARA SEGUIMIENTO DE PACIENTES CON DIABETES

**Resumen.** El presente trabajo expone un sistema multi-agente de soporte clínico para el seguimiento de pacientes con diabetes tipo 2. El sistema está compuesto por dos agentes especializados coordinados por un agente orquestador: un Agente Monitor que analiza métricas clínicas mediante herramientas de cálculo determinístico, y un Agente Clínico que interpreta los hallazgos consultando guías médicas oficiales y el historial acumulativo del paciente. En esta primera entrega se define el problema, el ambiente en el que opera el agente, la arquitectura general del sistema, el flujo de interacción con el médico y las herramientas que cada agente puede invocar. El sistema está concebido estrictamente como soporte a la decisión médica y no emite diagnósticos.

# 1. Introducción

El seguimiento de pacientes con diabetes tipo 2 requiere el monitoreo continuo de múltiples métricas clínicas cuya interpretación conjunta es compleja y propensa a errores por omisión. Un médico que atiende a decenas de pacientes crónicos necesita identificar rápidamente tendencias preocupantes, valores fuera de rango y contexto clínico relevante antes de cada consulta. Sin herramientas de soporte, este análisis se realiza manualmente a partir de registros dispersos, con riesgo de pasar por alto señales de alerta.

La diabetes es la condición crónica más prevalente a nivel mundial y una de las mejor documentadas en términos de guías clínicas estandarizadas. Los umbrales de diagnóstico y de control están definidos con precisión por la American Diabetes Association (ADA), lo que favorece la construcción de un sistema de soporte basado en reglas determinísticas complementadas con razonamiento en lenguaje natural.

El trabajo propone un sistema multi-agente orientado al soporte clínico en el seguimiento de pacientes con diabetes. El sistema recibe el historial de métricas clínicas de un paciente (glucosa en ayunas, HbA1c, glucosa postprandial, peso, presión arterial y medicación; los datos de monitoreo continuo CGM quedan como extensión futura) y lo analiza de forma autónoma en dos etapas coordinadas por un agente orquestador: un Agente Monitor que procesa los datos mediante herramientas de cálculo determinístico para detectar anomalías y violaciones de umbrales, y un Agente Clínico que interpreta los hallazgos consultando el historial acumulativo del paciente y las guías clínicas oficiales a través de RAG (Retrieval Augmented Generation). El resultado es un reporte estructurado que incluye alertas, tendencias y preguntas de seguimiento sugeridas, concebido como soporte a la decisión médica.

# 2. Solución

## 2.1 Descripción general del problema y objetivo del agente

**Problema:** dado el historial clínico de un paciente con diabetes (series temporales de glucosa, HbA1c, medicación activa y otras métricas relevantes), el médico necesita identificar si el paciente está en buen control metabólico, si hay tendencias preocupantes, y qué acciones clínicas son recomendables según las guías vigentes.

**Objetivo del agente:** analizar automáticamente el historial del paciente, detectar valores fuera de rango y tendencias anómalas, consultar guías clínicas para contextualizar los hallazgos, y producir un reporte estructurado de soporte para el médico tratante.

**Alcance explícito:** el sistema opera como herramienta de soporte a la decisión clínica. No emite diagnósticos. Toda salida incluye la aclaración "Este reporte es un insumo de soporte y no reemplaza el criterio del médico tratante."

## 2.2 Ambiente del agente

El agente opera en un ambiente:

- **Parcialmente observable:** accede al historial registrado del paciente y al historial acumulativo de sesiones anteriores, pero no puede observar el estado clínico en tiempo real ni factores no registrados como dieta, nivel de estrés, adherencia a la medicación o síntomas relatados en la consulta que el médico no haya ingresado explícitamente.
- **Estático durante la ejecución:** los datos del paciente no cambian mientras el agente los procesa. La actualización del historial ocurre únicamente al cierre de la sesión y con confirmación explícita del médico.
- **Output mixto:**
  - **Determinístico en la capa de datos:** dado el mismo historial, las tools de cálculo producen siempre el mismo resultado.
  - **Estocástico en la capa de razonamiento:** el LLM puede producir interpretaciones con variabilidad entre ejecuciones.
- **Secuencial con memoria de sesión y entre sesiones:** dentro de una sesión, el agente recuerda el paciente activo, las métricas ya calculadas y el historial de conversación con el médico. Entre sesiones, el historial acumulativo del paciente persiste en la base de datos y es recuperable en cada nueva consulta.
- **Discreto:** se puede definir un conjunto finito de percepciones y acciones para el agente que actúa en el ambiente.
- **Multiagente cooperativo:** intervienen tres agentes (Orquestador, Monitor y Clínico) que colaboran en pos del objetivo común, que es producir un reporte de soporte útil para el médico tratante.

**Percepciones del agente:**

- Historial de métricas clínicas del paciente cargadas desde el EHR (Electronic health record), como por ejemplo glucosa en ayunas, HbA1c, glucosa postprandial, peso o presión arterial.
- Series temporales de monitoreo continuo de glucosa (CGM), cuando el paciente dispone del dispositivo. *(Extensión futura: fuera del alcance de la implementación actual.)*
- Esquema de medicación activa con dosis y frecuencia.
- Historial acumulativo de sesiones anteriores con el sistema.
- Orientación del médico: instrucción opcional en lenguaje natural.
- Contexto clínico adicional: información del relato del paciente en la consulta actual que no figura en ningún sistema externo.
- Preguntas o aclaraciones del médico durante el chat de seguimiento.
- Fragmentos recuperados de guías clínicas (vía RAG).
- Outputs de cada tool invocada.

**Acciones del agente:**

- Invocar tools de cálculo y análisis sobre los datos del paciente.
- Calcular métricas de variabilidad glucémica a partir de datos CGM. *(Extensión futura.)*
- Recuperar el historial acumulativo completo del paciente por ID.
- Comparar métricas de la sesión actual con sesiones anteriores.
- Realizar búsquedas en la base de guías clínicas (RAG).
- Generar reportes estructurados.
- Responder preguntas de seguimiento del médico en el chat, acotadas al paciente activo.
- Registrar la sesión actual en el historial acumulativo, únicamente con confirmación explícita del médico.
- Solicitar aclaraciones al médico si la consulta es ambigua.
- Registrar alertas con nivel de urgencia.

## 2.3 Arquitectura general

El sistema implementa una arquitectura multi-agente orquestada mediante LangGraph (se usa LangGraph porque el flujo requiere ciclos condicionales entre agentes; LangChain provee las integraciones con los servicios externos), con un estado compartido que fluye entre los nodos. Sobre los dos agentes especializados, Monitor y Clínico, se incorpora un Agente Orquestador que coordina el flujo y decide qué agente debe intervenir en cada momento.

### Arquitectura general del sistema de soporte clínico

#### Componentes principales

La arquitectura está compuesta por tres tipos de actores: el médico, que inicia la interacción; un agente orquestador, que decide cómo se procesa cada consulta; y dos agentes especializados, el Agente Monitor y el Agente Clínico, cada uno con un foco de análisis distinto. A esto se suman tres fuentes de datos externas que los agentes consultan durante su procesamiento.

#### Flujo de la consulta

El médico envía una consulta al agente orquestador, acompañada opcionalmente de orientación sobre el análisis o contexto clínico adicional. A partir de esta consulta, el orquestador decide el camino a seguir, lo que constituye el punto central de control de la arquitectura: en lugar de que toda solicitud pase siempre por el mismo procesamiento, el sistema adapta el recorrido según la naturaleza de la pregunta.

El orquestador no usa comandos explícitos, sino que **infiere la intención** a partir del mensaje del médico y del estado actual de la sesión (si ya hay un reporte generado, si es una pregunta de seguimiento, si se pide reiniciar, etc.). En función de esa inferencia elige el camino. Los dos caminos principales son:

- **Flujo completo:** ante una consulta nueva sin reporte previo, la consulta pasa primero por el Agente Monitor, cuya función es responder a la pregunta ¿qué dicen los números?, es decir, realizar un análisis cuantitativo de los datos disponibles. Los hallazgos de este análisis se entregan luego al Agente Clínico, que se encarga de responder ¿qué significan?, interpretando esos hallazgos en el contexto clínico del paciente. Es el comportamiento por defecto.
- **Derivación directa al Agente Clínico:** cuando ya existe un reporte en el estado y el médico formula una pregunta de seguimiento sobre él, el orquestador deriva la consulta directamente al Agente Clínico, sin pasar por el Agente Monitor, ya que los hallazgos cuantitativos ya están disponibles y solo se requiere interpretación o consulta a guías/historial.

#### ¿Alcanza la información?

Después de que el Agente Clínico procesa la información (ya sea proveniente del Agente Monitor o recibida en una derivación directa), el sistema evalúa si la información disponible es suficiente para generar una respuesta de soporte. El Agente Clínico expone esta evaluación mediante una señal explícita (`information_sufficient`) que el orquestador lee. Esta evaluación da lugar a dos resultados posibles:

- Si la información no alcanza, el flujo vuelve al agente orquestador, que devuelve el control al Agente Monitor para recalcular o ampliar el análisis (o solicita información adicional al médico). Este bucle existe para que el sistema pueda corregir su propio recorrido cuando el primer intento resulta insuficiente, en lugar de entregar una respuesta incompleta, y está acotado por el límite de iteraciones definido en los guardrails (máximo 3).
- Si la información alcanza, el sistema genera un reporte de soporte, que constituye la salida final entregada al médico.

#### Fuentes de datos consultadas por los agentes

Cada agente especializado consulta fuentes de datos externas específicas, lo que define su ámbito de trabajo:

- El Agente Monitor consulta los datos del paciente provenientes del EHR (y, como extensión futura, del sensor de monitoreo continuo de glucosa, CGM). Esta fuente le provee la información cuantitativa necesaria para su análisis de números.
- El Agente Clínico consulta el historial de sesiones previas del paciente, lo que le permite realizar comparaciones longitudinales y mantener continuidad entre consultas.
- El Agente Clínico también consulta guías clínicas de referencia (ADA, SAD, MSAL), que le proporcionan el marco normativo y de buenas prácticas necesario para interpretar los hallazgos dentro de estándares reconocidos.

La separación de estas fuentes por agente refleja una división de responsabilidades: el Agente Monitor trabaja sobre datos crudos y en tiempo real del paciente, mientras que el Agente Clínico trabaja sobre conocimiento acumulado (historial y guías) para dar sentido a esos datos.

**¿Por qué un agente orquestador explícito?**
Se decide incorporar un Agente Orquestador porque aporta dos capacidades que un encadenamiento rígido no ofrece. En primer lugar, permite enrutar selectivamente el trabajo: no toda consulta del médico requiere ejecutar la totalidad del pipeline. En segundo lugar, habilita la corrección del recorrido mediante el loop de refinamiento, devolviendo el control a un agente anterior cuando la información resulta insuficiente.

El enrutamiento se decide por **inferencia de intención**: el orquestador lee el mensaje del médico y el estado de la sesión, y a partir de ahí determina el camino, sin requerir que el médico escriba comandos explícitos. Los criterios de decisión son:

- **Consulta nueva (sin reporte previo):** el orquestador ejecuta la secuencia completa Monitor → Clínico. Es el comportamiento por defecto.
- **Pregunta de seguimiento (con reporte ya generado):** el orquestador deriva directamente al Agente Clínico, sin recalcular, asumiendo que los hallazgos cuantitativos ya están en el estado de la sesión.
- **Pedido de reiniciar o analizar un nuevo paciente:** el orquestador limpia el estado y vuelve a ejecutar el flujo completo.
- **Confirmación de guardado:** el orquestador invoca la persistencia de la sesión.
- **Mensaje ambiguo:** el orquestador solicita una aclaración antes de proceder.

El orquestador es responsable, además, de gestionar el **loop de refinamiento**: si el Agente Clínico señala (mediante `information_sufficient = False`) que la información recibida del Monitor es insuficiente para interpretar un hallazgo, el orquestador devuelve el control al Monitor para recalcular o ampliar el análisis, respetando el límite de iteraciones definido en los guardrails (máximo 3). Esta lógica de decisión (cuándo basta con un agente, cuándo se requiere el flujo completo y cuándo conviene refinar) es motivo para que el orquestador sea un componente propio y no quede embebido en transiciones fijas del grafo.

### Componentes adicionales

Los siguientes módulos serán detallados en entregas posteriores. Se describen aquí a nivel de tecnología y propósito para dar una visión completa del sistema.

**Loop del agente:** se implementa el patrón **ReAct** (Reasoning + Acting). Cada agente razona qué acción tomar, ejecuta una tool, observa el resultado y decide el paso siguiente. LangGraph gestiona el flujo entre nodos y el límite de iteraciones, bajo la coordinación del Agente Orquestador.

**Memoria:** el sistema distingue dos niveles de memoria.

- **Memoria de sesión:** estado nativo del grafo LangGraph. Dentro de una sesión, los agentes comparten el paciente activo, las métricas ya calculadas y el historial de conversación con el médico.
- **Memoria persistente entre sesiones:** historial acumulativo del paciente almacenado en una base de datos. Cada sesión se registra como un nodo estructurado dentro del documento del paciente, recuperable en consultas futuras mediante búsqueda exacta por identificador.

**Historial del paciente:** se almacena en **MongoDB** (base NoSQL documental) donde cada paciente tiene un documento que se actualiza sesión a sesión. La recuperación es exacta por identificador (DNI o ID interno), no mediante RAG: dado el alcance del trabajo y el volumen de sesiones por paciente, indexar el historial propio en una base vectorial introduciría complejidad adicional.

**RAG:** las guías clínicas (ADA, Sociedad Argentina de Diabetes, Ministerio de Salud Argentina) se indexan en ChromaDB usando embeddings nomic-embed-text vía Ollama. El Agente Clínico consulta esta base exclusivamente para las guías clínicas y contextualiza cada hallazgo con fragmentos relevantes de las guías oficiales.

**Guardrails:**

- Límite de 3 iteraciones entre agentes.
- Validación de inputs antes de invocar tools.
- La tool de actualización del historial requiere confirmación explícita del médico antes de ejecutarse; disclaimer obligatorio en todo reporte generado por el Agente Clínico.

**Observabilidad:** se utiliza **LangSmith** para trazas estructuradas, registrando prompts, respuestas, invocaciones a tools y fragmentos RAG recuperados. Como fallback, logging propio en JSON.

**Interfaz:** Streamlit o Gradio para la interacción del médico con el sistema.

## 2.4 Flujo de interacción médico–sistema

La interacción entre el médico y el sistema sigue una secuencia de etapas dentro de una sesión, representada en la Figura 2. Se describe a continuación cada etapa en orden cronológico.

**Figura 2.** Flujo de interacción entre el médico y el sistema.

**1. Selección del paciente y carga de datos.** El médico selecciona al paciente en la interfaz. El sistema carga automáticamente el historial clínico desde el EHR externo (glucosa, HbA1c, peso, presión arterial, medicación) y, como extensión futura, si el paciente dispone de dispositivo CGM, las series temporales de monitoreo continuo. En paralelo, el Agente Clínico recupera el historial acumulativo de sesiones anteriores desde la base de datos interna.

**2. Revisión del perfil resumido.** El sistema presenta un resumen del paciente que permite al médico contextualizar la consulta antes de lanzar el análisis.

**3. Ingreso de orientación y contexto clínico adicional.** Antes de lanzar el análisis, el médico dispone de dos campos opcionales distintos:

- **Orientación del análisis:** instrucción en lenguaje natural que indica el foco de la sesión. El orquestador la interpreta junto con la consulta para inferir el enrutamiento.
- **Contexto clínico adicional:** información del relato del paciente en la consulta actual que no figura en el EHR ni en el CGM, como síntomas recientes, eventos intercurrentes (infección, cirugía, estrés), adherencia referida o cambios de dieta y actividad física. Este campo no es una instrucción al agente, sino un dato clínico que el Agente Clínico incorpora como contexto interpretativo para las búsquedas en las guías.

**4. Ejecución del flujo de agentes.** El médico lanza el análisis y el Agente Orquestador enruta el trabajo según la intención inferida. En el flujo completo, el Agente Monitor procesa los datos cuantitativos y el Agente Clínico interpreta los hallazgos consultando el historial acumulativo, comparando con sesiones anteriores y realizando búsquedas semánticas sobre las guías. Si se trata de una pregunta de seguimiento sobre un reporte ya generado, el orquestador deriva directamente al Agente Clínico.

**5. Revisión del reporte y chat de seguimiento.** La interfaz presenta el reporte en un layout de panel dividido: el reporte ocupa el panel principal y el chat de seguimiento queda disponible en un panel secundario, de modo que el médico pueda formular preguntas sin perder de vista el reporte. El chat está acotado al paciente activo de la sesión: el Agente Clínico mantiene en contexto el estado completo del análisis y responde usando los datos del paciente ya cargados. Si el médico formula una pregunta sin relación con los datos del paciente activo, el sistema lo indica y reconduce la interacción.

**6. Cierre de sesión y actualización del historial.** Al cerrar la sesión, el sistema ofrece al médico la opción de guardar el resumen de la sesión actual en el historial acumulativo del paciente. La escritura no ocurre automáticamente: requiere confirmación explícita, dado que el médico puede haber ajustado su interpretación durante la consulta y el reporte del agente no debería registrarse sin revisión.

## 2.5 Historial acumulativo del paciente

El historial del paciente se almacena en **MongoDB** como un documento por paciente, identificado por DNI o ID interno, que se actualiza sesión a sesión. Se eligió una base NoSQL documental (MongoDB) frente a la alternativa de PostgreSQL con columnas JSON/JSONB porque el patrón de uso es una búsqueda exacta por identificador que recupera el documento completo del paciente, sin necesidad de consultas relacionales.

Se decide **no usar RAG** para el historial del paciente, por dos motivos:

1. Cuando el Agente Clínico necesita el historial, lo necesita completo, fragmentarlo en vectores introduciría el riesgo de recuperar partes de sesiones anteriores que contradigan el estado actual, o incluso fragmentos de otro paciente con perfil clínico similar.
2. Para el volumen esperado en un seguimiento común (una consulta cada algunos meses, durante dos o tres años, ocho a doce sesiones por paciente), el documento completo ocupa pocos kilobytes y cargarlo entero en el contexto del modelo es factible y más confiable que una recuperación con RAG.

Cada sesión queda registrada como un nodo dentro de un arreglo, con su fecha, la orientación y el contexto que ingresó el médico, los hallazgos del Monitor, la interpretación del Clínico, las alertas y las preguntas sugeridas. De esta forma, en cada nueva consulta el Agente Clínico puede recuperar el documento completo y comparar el estado actual con el de sesiones previas sin depender de embeddings.

## 2.6 Agentes y Tools

### Agente Orquestador

Responsable de coordinar el flujo entre los agentes especializados. Recibe la consulta del médico, infiere su intención a partir del mensaje y del estado de la sesión, y enruta el trabajo en consecuencia: hacia el flujo completo Monitor → Clínico ante una consulta nueva, o directamente al Agente Clínico ante una pregunta de seguimiento sobre un reporte ya generado. Gestiona además el loop de refinamiento entre agentes dentro del límite de iteraciones definido en los guardrails. No invoca tools de datos por sí mismo ya que su responsabilidad es de decisión y enrutamiento.

### Agente Monitor

Responsable del análisis cuantitativo. No realiza interpretaciones clínicas: solo procesa datos y devuelve resultados estructurados. Todas sus tools son determinísticas:

**Tool 1: `load_patient_data(patient_id: str) → dict`**

Carga el historial clínico del paciente desde el EHR externo (CSV o SQLite). Devuelve un diccionario con series temporales de glucosa en ayunas, HbA1c, glucosa postprandial, peso y presión arterial.

**Tool 2: `calculate_stats(metric: str, values: list, timerange: str) → dict`**

Calcula media, desviación estándar, tendencia lineal (pendiente) y último valor registrado para una métrica dada en el rango temporal especificado.

**Tool 3: `detect_threshold_violations(metric: str, values: list) → list`**

Compara cada valor contra los umbrales clínicos de la ADA y devuelve una lista de violaciones con timestamp, valor y severidad (leve / moderada / severa). Umbrales leídos desde un documento común que tenga los lineamientos ADA:

| Métrica | Normal | Alerta | Crítico |
|---|---|---|---|
| Glucosa ayunas (mg/dL) | < 100 | 100–125 | ≥ 126 |
| HbA1c (%) | < 5.7 | 5.7–6.4 | ≥ 6.5 |
| Glucosa postprandial (mg/dL) | < 140 | 140–199 | ≥ 200 |

**Tool 4: `get_medication_schedule(patient_id: str) → list`**

Devuelve la medicación activa del paciente con dosis y frecuencia.

**Tool 5: `analyze_cgm_data(cgm_series: list, timerange: str) → dict`** *(Extensión futura — fuera del alcance de la implementación actual.)*

Procesa las series temporales de monitoreo continuo de glucosa (CGM) cuando el paciente dispone del dispositivo. Esta tool existe porque los datos CGM tienen naturaleza distinta a las glucemias puntuales del EHR: son series densas, con una lectura cada cinco a quince minutos, que requieren métricas específicas. Devuelve el tiempo en rango (TIR, porcentaje de lecturas entre 70 y 180 mg/dL), el tiempo por debajo y por encima del rango (TBR y TAR, con desagregación por severidad), el coeficiente de variación glucémica (un CV ≥ 36 % indica alta variabilidad independientemente del promedio), la cantidad de episodios de hipoglucemia nocturna y la glucosa media del período con su equivalente estimado de HbA1c. Es determinística: dada la misma serie, produce siempre el mismo resultado.

**Output del Agente Monitor:** un objeto con estadísticas por métrica, lista de violaciones detectadas, medicación activa, métricas CGM cuando aplican *(extensión futura)*, y dos flags para el Agente Clínico: `requires_rag`, que indica que hay alertas moderadas o severas y amerita consultar las guías clínicas, y `requires_longitudinal_comparison`, que indica si el Agente Clínico debería comparar alguna métrica con sesiones anteriores.

### Agente Clínico

Recibe el output estructurado del Agente Monitor e interpreta los hallazgos en términos médicos, incorporando el historial acumulativo del paciente, la comparación longitudinal entre sesiones y la consulta a guías clínicas oficiales. Es también el agente que responde las preguntas del médico durante el chat de seguimiento.

**Tool 6: `get_patient_history(patient_id: str) → dict`**

Recupera el historial acumulativo completo del paciente desde la base de datos interna, identificado por DNI o ID interno. Devuelve el documento íntegro: datos demográficos, diagnósticos, comorbilidades, medicación base y el arreglo de sesiones anteriores con sus fechas, hallazgos, interpretaciones y alertas. El Agente Clínico la invoca al inicio de su razonamiento, antes de generar cualquier interpretación, para disponer del contexto del paciente.

**Tool 7: `compare_with_previous_sessions(patient_id: str, metric: str, n_sessions: int) → dict`**

Compara el valor actual de una métrica con el de las últimas n_sessions sesiones registradas en el historial acumulativo. Es una tool determinística que opera por cálculo sobre el documento ya recuperado, sin invocar al modelo de lenguaje. Extrae los valores de la métrica con su fecha, calcula el delta respecto de la sesión anterior y la pendiente de la tendencia cuando hay tres o más puntos, y clasifica la evolución como mejorando, estable o deteriorando según umbrales clínicos por métrica. Su propósito es forzar un razonamiento longitudinal explícito y auditable: la interpretación de una métrica fuera de rango cambia según venga mejorando o empeorando respecto de visitas previas. El Agente Clínico no la invoca en todas las sesiones, sino cuando el Monitor señala una violación o tendencia anómala; esa selectividad es parte de su razonamiento ReAct. La comparación corresponde al Agente Clínico y no al Monitor porque opera sobre los resúmenes clínicos de sesiones anteriores, no sobre las series de datos crudos.

**Tool 8: `search_clinical_guidelines(condition: str, value: float, context: str) → list[str]`**

Realiza búsqueda semántica sobre la base vectorial de guías clínicas indexadas en ChromaDB. Devuelve los fragmentos más relevantes según la condición y el valor detectado. El parámetro `context` incorpora el texto del campo de contexto clínico adicional ingresado por el médico, lo que permite que el agente module el query antes de invocar la tool: si el médico indicó, por ejemplo, una insuficiencia renal leve, el agente orienta la búsqueda hacia los fragmentos pertinentes a esa condición. La búsqueda es determinística dado el mismo query y la misma base indexada.

**Fuentes indexadas:**

- ADA Standards of Medical Care in Diabetes.
- Guías de la Sociedad Argentina de Diabetes (SAD).
- Guía de práctica clínica del Ministerio de Salud de la Nación Argentina sobre diabetes tipo 2.

**Tool 9: `update_patient_history(patient_id: str, session_data: dict) → bool`**

Escribe la sesión actual como un nuevo nodo en el arreglo de sesiones del documento de historial del paciente, y devuelve la confirmación de la escritura. Esta tool no se ejecuta automáticamente al finalizar el flujo: queda disponible para ser invocada únicamente cuando el médico confirma de forma explícita en la interfaz que el resumen de la sesión puede guardarse. La razón es que el médico puede haber ajustado su interpretación durante la consulta, y registrar el reporte del agente como historial oficial sin revisión introduciría ruido en la base de datos que alimenta el razonamiento de sesiones futuras. El campo `session_data` reúne la fecha, la orientación y el contexto ingresados por el médico, los hallazgos del Monitor, las métricas CGM, la comparación longitudinal, la interpretación clínica, las alertas y las preguntas sugeridas.

**Output del Agente Clínico:** reporte clínico estructurado con resumen del estado metabólico del paciente, evaluación de la tendencia longitudinal cuando aplica, alertas con nivel de urgencia, interpretación de cada hallazgo con cita de la guía de referencia, preguntas de seguimiento sugeridas para el médico, y nota aclaratoria sobre que es solo para soporte a la decisión.

## 2.7 Stack tecnológico

| Componente | Tecnología |
|---|---|
| Orquestación de agentes | LangGraph + LangChain |
| LLM | Groq API — llama-3.3-70b |
| Embeddings | Ollama — nomic-embed-text |
| Vector store (solo guías clínicas) | ChromaDB |
| Historial de pacientes | MongoDB (NoSQL documental) |
| Validación de outputs | Pydantic v2 |
| Interfaz | Streamlit/Gradio |
| Observabilidad | LangSmith |
| Datos pacientes | Datos sintéticos (Faker) |
| Control de versiones | GitHub |

# 3. Conclusiones

Elegimos diabetes porque los umbrales de la ADA nos permiten hacer las tools determinísticas, lo que nos pareció importante para un dominio médico. La separación en dos agentes especializados surgió de querer distinguir el análisis numérico de la interpretación, y la incorporación del agente orquestador nos permite enrutar el flujo de forma selectiva, infiriendo la intención del médico para ejecutar el pipeline completo, derivar a una respuesta de seguimiento o refinar el análisis cuando la información resulta insuficiente. La decisión de almacenar el historial del paciente en una base de datos (y no mediante RAG) responde a simplificar el alcance del trabajo y a que el historial se necesita íntegro.
