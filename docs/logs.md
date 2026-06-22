# Guía de logs (observabilidad)

Cómo leer las trazas que genera el sistema. Hay **dos formatos del mismo evento**:
la **consola** (legible, en vivo) y el archivo **`logs/agent.jsonl`** (estructurado, para análisis).

Configuración en [interface/logging_config.py](../interface/logging_config.py).

---

## En la terminal

Formato: `HORA [evento] resumen`

```
13:38:40 [node_start] Nodo start: orchestrator          ← entró al Orquestador (clasifica intención)
13:38:40 [routing]    Routing: route_from_orchestrator  ← decidió el camino (pipeline/followup/save)
13:38:40 [node_start] Nodo start: monitor               ← corrió el Monitor (análisis cuantitativo)
13:38:40 [node_start] Nodo start: clinical              ← corrió el Clínico (interpretación/reporte)
13:38:40 [routing]    Routing: decide_next              ← decidió si refina (vuelve al Monitor) o termina
```

Esa secuencia es una **consulta nueva → pipeline completo**.
Un follow-up se ve como `orchestrator → routing → clinical` (sin `monitor`).

---

## En el archivo `logs/agent.jsonl`

Cada línea es **un evento = un objeto JSON**. Campos:

| Campo | Significado |
|---|---|
| `ts` | Timestamp ISO 8601 **en UTC** con milisegundos |
| `level` | Nivel de logging (`INFO`) |
| `event` | Tipo de evento (ver tabla abajo) |
| `name` | Nombre del componente (nodo, función de routing, modelo o tool) |
| `node` | Solo en `routing`: a qué nodo pertenece esa decisión |
| `run_id` | UUID único de ese paso. Sirve para **correlacionar** start/end del mismo paso y cruzar con LangSmith |

Verlo formateado:

```bash
cat logs/agent.jsonl | jq
```

---

## Tipos de evento (`event`)

| Evento | Cuándo aparece |
|---|---|
| `node_start` | Empieza a ejecutarse un nodo del grafo |
| `routing` | Corre una función de decisión (`route_from_orchestrator`, `decide_next`) |
| `llm_start` / `llm_end` | Llamada al LLM. `llm_end` incluye el conteo de **tokens** (prompt/completion). Requiere `GROQ_API_KEY` |
| `tool_start` / `tool_end` | Invocación a una tool. `tool_start` registra el **nombre de la tool** y su **input**; `tool_end`, el **output** |
| `llm_error` / `tool_error` | Error durante una llamada al LLM o a una tool |

> Con `GROQ_API_KEY` configurada, el grafo usa los agentes reales y verás la secuencia completa
> (`node_start` → `tool_start`/`tool_end` → `llm_start`/`llm_end`). Sin la key, el grafo cae a sus
> fallbacks determinísticos y solo verás `node_start` y `routing`.

---

## Tres detalles importantes

1. **La hora difiere entre consola y archivo a propósito**: la consola usa hora **local**
   (ej. 13:38, Argentina UTC−3) y el archivo usa **UTC** (ej. 16:38). UTC es el estándar
   para logs que después se comparan u ordenan entre máquinas.
2. **El archivo se acumula** entre ejecuciones (modo append): vas a ver corridas distintas
   juntas. Rota automáticamente al llegar a 5 MB (se conservan 3 archivos).
3. La riqueza del log depende de si hay `GROQ_API_KEY`: con los **agentes reales** vas a ver
   `llm_*` y `tool_*`; con el **fallback determinístico** (sin key) solo `node_start` y `routing`.

> El `StarletteDeprecationWarning` al levantar Gradio es ruido interno de la librería, no del
> código del proyecto — inofensivo.

---

## LangSmith

En paralelo, las trazas también se envían a **LangSmith** (proyecto `tp2-diabetes`) si están
configuradas las variables `LANGSMITH_*` en `.env`. Da una vista visual del grafo, tiempos y
—cuando se conecten— prompts/respuestas del LLM. El archivo JSONL es el fallback local.
