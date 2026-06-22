# TP2 — Sistema Multi-Agente de Soporte Clínico para Diabetes

Sistema multi-agente (LangGraph) de **soporte a la decisión clínica** para seguimiento de
pacientes con diabetes tipo 2. Tres agentes coordinados (Orquestador, Monitor y Clínico)
analizan el historial del paciente, detectan valores fuera de rango y producen un reporte
estructurado consultando guías clínicas (RAG). **No emite diagnósticos.**

Diseño completo en [docs/TP_2.1 Definicion Conceptual.md](docs/TP_2.1%20Definicion%20Conceptual.md).

## Requisitos previos

- **[uv](https://docs.astral.sh/uv/)** (gestor de entorno y dependencias). Python 3.12+ lo
  instala uv automáticamente.
- *(Para correr el pipeline completo con datos reales; sin ellos, el grafo cae a fallbacks
  determinísticos y la UI funciona sobre el fixture `data/sample/`)*:
  - **Groq API key** - LLM (`llama-3.3-70b`) de los agentes Monitor y Clínico.
  - **[Ollama](https://ollama.com/)** con el modelo `nomic-embed-text` - embeddings del RAG.
  - **MongoDB** (instancia local; Docker es lo más simple) - historial de pacientes.
  - **LangSmith API key** *(opcional)* - observabilidad.

  Preparación de datos (una vez): `uv run python data/load_mongo.py` (carga MongoDB) y
  `uv run python rag/ingest.py` (indexa las guías en ChromaDB).

## Ejecutar

```bash
uv sync                          # 1. instalar dependencias (crea el .venv)
cp .env.example .env             # 2. configurar entorno y completar GROQ_API_KEY
uv run pytest                    # 3. correr los tests (esqueleto del grafo end-to-end)
uv run python -m interface.app   # 4. levantar la interfaz web (http://127.0.0.1:7860)
```

En Windows, el paso 2 es `Copy-Item .env.example .env`.

La interfaz tiene dos pestañas: **Consulta clínica** (selección de paciente, análisis, reporte
y chat de seguimiento) y **Observabilidad (dev)** (visor del log estructurado). Ver
[docs/interfaz.md](docs/interfaz.md) y [docs/logs.md](docs/logs.md).

## Estructura del repo

```
orchestrator/   state.py (estado + modelos) · graph.py (grafo) · router.py (routing heurístico)
agents/         prompts.py · monitor.py (ReAct) · clinical.py (ReAct)
tools/          patient_tools.py · threshold_tools.py · mongo_tools.py · rag_tools.py
rag/            ingest.py (ChromaDB) · retriever.py
data/           generate_patients.py · load_mongo.py · guias/ · sample/
interface/      app.py (UI Gradio) · components.py (render) · logging_config.py (logs)
tests/          test_graph.py · test_monitor_tools.py · test_tools.py · cases/   (cases: pendiente)
docs/           definición conceptual, enunciado, división de trabajo, tareas
```

## Comandos

```bash
uv sync                 # instalar / actualizar el entorno
uv run pytest           # correr los tests
uv lock                 # regenerar el lockfile tras cambiar dependencias en pyproject.toml
```
