# TP2 — Sistema Multi-Agente de Soporte Clínico para Diabetes

Sistema multi-agente (LangGraph) de **soporte a la decisión clínica** para seguimiento de
pacientes con diabetes tipo 2. Tres agentes coordinados (Orquestador, Monitor y Clínico)
analizan el historial del paciente, detectan valores fuera de rango y producen un reporte
estructurado consultando guías clínicas (RAG). **No emite diagnósticos.**

Diseño completo en [docs/TP_2.1 Definicion Conceptual.md](docs/TP_2.1%20Definicion%20Conceptual.md).

## Requisitos previos

- **[uv](https://docs.astral.sh/uv/)** (gestor de entorno y dependencias). Python 3.12+ lo
  instala uv automáticamente.
- *(Para los módulos en desarrollo, aún no necesarios para correr lo que ya existe)*:
  - **Groq API key** - LLM (`llama-3.3-70b`).
  - **[Ollama](https://ollama.com/)** con el modelo `nomic-embed-text` - embeddings del RAG.
  - **MongoDB** (instancia local; Docker es lo más simple) - historial de pacientes.
  - **LangSmith API key** *(opcional)* - observabilidad.

## Ejecutar

```bash
uv sync                          # 1. instalar dependencias (crea el .venv)
cp .env.example .env             # 2. configurar entorno y completar GROQ_API_KEY
uv run pytest                    # 3. correr los tests (esqueleto del grafo end-to-end)
```

En Windows, el paso 2 es `Copy-Item .env.example .env`.

## Estructura del repo

```
orchestrator/   state.py (estado + modelos) · graph.py (grafo) · router.py (routing)
agents/         prompts.py · monitor.py · clinical.py        (agentes: en desarrollo)
tools/          patient_tools.py · threshold_tools.py · rag_tools.py   (en desarrollo)
rag/            ingest.py · retriever.py                     (en desarrollo)
data/           generate_patients.py                         (en desarrollo)
interface/      app.py · components.py · logging_config.py   (en desarrollo)
tests/          test_graph.py · test_tools.py · cases/   (parcial)
docs/           definición conceptual, enunciado, división de trabajo, tareas
```

## Comandos

```bash
uv sync                 # instalar / actualizar el entorno
uv run pytest           # correr los tests
uv lock                 # regenerar el lockfile tras cambiar dependencias en pyproject.toml
```
