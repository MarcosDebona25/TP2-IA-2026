# RAG — Guía de parámetros tunables

Referencia rápida para ajustar la calidad del pipeline RAG sin tener que leer
el código. Cada parámetro indica en qué archivo vive y qué efecto produce.

**Regla general:** después de cambiar cualquier parámetro de ingestión
(`CHUNK_SIZE`, `CHUNK_OVERLAP`, `SEPARATORS`, `EMBEDDING_MODEL`), hay que
borrar `data/chroma_db/` y volver a correr `uv run python rag/ingest.py`.
Los parámetros de retrieval (`k`, `DISTANCE_THRESHOLD`) no requieren re-ingestión.

---

## Ingestión (`rag/ingest.py`)

### `EMBEDDING_MODEL`
Modelo que convierte texto en vectores numéricos.

| Valor | Dimensión | Cuándo usarlo |
|---|---|---|
| `"nomic-embed-text"` (default) | 768 | Buena calidad, liviano, corre en CPU |
| `"mxbai-embed-large"` | 1024 | Mejor calidad semántica, más lento |

Cambiar el modelo requiere re-ingestión completa (los vectores son incompatibles).
Instalar con: `ollama pull <nombre-del-modelo>`.

---

### `CHUNK_SIZE`
Cuántos **caracteres** entra en cada fragmento.

| Valor | Efecto |
|---|---|
| 200–300 | Fragmentos muy precisos; riesgo de partir definiciones |
| **500 (default)** | Balance entre precisión y contexto |
| 800–1000 | Más contexto por chunk; el embedding puede "diluir" el tema principal |

Para guías médicas con tablas de umbrales y criterios diagnósticos, valores entre
400 y 600 dan mejores resultados que valores extremos.

---

### `CHUNK_OVERLAP`
Cuántos caracteres se repiten entre chunks consecutivos.

| Valor | Efecto |
|---|---|
| 0 | Sin solapamiento; mayor riesgo de partir conceptos en el corte |
| **50 (default)** | ~10% del chunk; preserva la continuidad en la mayoría de los casos |
| 100–150 | Mayor redundancia en el índice; útil si los conceptos son muy densos |

Regla práctica: mantener el overlap entre el 10% y el 20% del `CHUNK_SIZE`.

---

### `SEPARATORS`
Orden de preferencia para decidir dónde cortar un chunk.

Default: `["\n## ", "\n### ", "\n\n", "\n", ". ", " "]`

El chunker intenta cortar en el primer separador que encuentra dentro del límite
de `CHUNK_SIZE`. Si las guías tienen una estructura de títulos consistente
(`## Sección`, `### Subsección`), estos separadores ya están cubiertos.

Ajustar si las guías usan otra convención (p. ej. títulos numerados `1.2.3`):
agregar el patrón como primer elemento de la lista.

---

### `hnsw:space` (función de distancia)
Define cómo ChromaDB mide la similitud entre vectores.

| Valor | Cuándo usarlo |
|---|---|
| `"cosine"` (default) | Texto: mide ángulo entre vectores, ignora magnitud |
| `"l2"` | Datos numéricos; menos adecuado para texto |
| `"ip"` | Inner product; útil con modelos entrenados con esta métrica |

Para embeddings de texto, `"cosine"` es casi siempre la mejor opción.
**Cambiar este valor requiere re-ingestión.**

---

## Retrieval (`rag/retriever.py`)

### `k` (top-k)
Cuántos fragmentos devolver por consulta.

| Valor | Efecto |
|---|---|
| 1–2 | Muy específico; puede perder contexto complementario |
| **3 (default)** | Balance estándar para la mayoría de las consultas |
| 5–6 | Más contexto; el prompt del LLM crece; puede incluir fragmentos irrelevantes |

El valor se puede ajustar por tipo de consulta: `k=2` para preguntas muy
concretas ("¿cuál es el umbral de HbA1c?"), `k=5` para consultas amplias
("¿qué dice la guía sobre el manejo integral del diabético tipo 2?").

---

### `DISTANCE_THRESHOLD`
Filtra fragmentos cuya distancia coseno supera este umbral.

Con `hnsw:space = "cosine"`, ChromaDB devuelve distancias en `[0, 2]`:
- `0` = vectores idénticos
- `1` = sin relación
- `2` = opuestos

| Valor | Efecto |
|---|---|
| `1.0` (default) | Sin filtro; acepta todos los resultados de ChromaDB |
| `0.7` | Descarta fragmentos con similitud menor al 30% |
| `0.5` | Solo fragmentos con alta similitud; puede devolver lista vacía |

Recomendación: empezar sin filtro (`1.0`) y, si el Agente Clínico recibe
fragmentos claramente irrelevantes, bajar a `0.7`.

---

## LangChain Tools (`tools/rag_tools.py`)

### `k` en `search_clinical_guidelines_tool` y `get_rag_context_tool`
Mismo parámetro que en retrieval, pero hardcodeado en la llamada al retriever.

Cambiar `k=3` por el valor deseado en cada tool según el caso de uso:
- `search_clinical_guidelines_tool`: devuelve lista; C la puede iterar.
- `get_rag_context_tool`: devuelve string formateado; más cómodo para un solo
  LLM call.

Considerar exponer `k` como parámetro de la tool si el Agente Clínico necesita
controlarlo dinámicamente según la complejidad de la consulta.

---

## Cómo evaluar si el RAG mejoró

1. Correr una consulta de prueba con `uv run python rag/retriever.py` (ver el
   bloque `__main__` del archivo).
2. Leer los fragmentos devueltos: ¿son relevantes para la pregunta?
3. Cambiar un parámetro, re-ingestar si corresponde, y repetir.
4. Cuando el sistema esté integrado, comparar reportes del Agente Clínico con
   y sin RAG para el mismo paciente.
