# ADR-0021 · DeepSeek directo con el razonamiento desactivado

- **Estado:** Aceptado
- **Fecha:** 2026-10-16
- **Relacionado:** [ADR-0020](0020-proveedores-openai-compatibles-y-cadena-entre-proveedores.md), [ADR-0019](0019-reporte-estructurado-y-generacion-anclada.md), [ADR-0015](0015-modo-lean-para-free-tier.md)

## Contexto

- Se usa la API de DeepSeek directa (`LLM_PROVIDER=openai_compat`, `LLM_BASE_URL=https://api.deepseek.com`).
- `GET /models` (2026-10-16) lista solo `deepseek-flash` (DeepSeek-V4.1-Flash) y `deepseek-v4-pro`. Los dos **razonan
  por defecto** (esfuerzo `high`). `deepseek-chat` ya no figura en la documentación: la API todavía lo acepta y responde
  con `deepseek-flash` sin razonamiento, pero es un alias heredado que puede desaparecer.
- La salida estructurada (`MonitorPlan`, `ClinicalReport`) usa `method="function_calling"` (ADR-0020), que fuerza
  `tool_choice` a una función. En modo razonamiento DeepSeek lo rechaza:
  `400 – Thinking mode does not support this tool_choice`. Medido con P002 y P005: con `deepseek-flash` y
  `deepseek-v4-pro` el Monitor y el reporte del Clínico cayeron al fallback; con razonamiento desactivado, ambos en
  modo `llm` (15–16 s por análisis, 10 s el seguimiento).
- En modo razonamiento además se ignora `temperature` (el sistema usa 0) y, en conversaciones con tools, hay que
  reenviar `reasoning_content` en cada llamada o la API responde 400; `langchain-openai` no lo garantiza.
- Al clasificar ese 400, `_fallback_reason` lo marcó como `rate_limit` porque el `request_id` contenía la cadena `429`.

## Decisión

1. Con `openai_compat`, `agents/llm_factory.thinking_mode()` envía `extra_body={"thinking": {"type": ...}}`:
   - si `LLM_BASE_URL` es de DeepSeek y `LLM_THINKING` no está definido → `disabled`;
   - `LLM_THINKING=enabled|disabled` lo fija explícitamente (para experimentos);
   - a otras APIs compatibles no se envía nada salvo que `LLM_THINKING` esté definido.
2. Modelo recomendado: `deepseek-flash` (nombre oficial) en lugar del alias `deepseek-chat`.
3. `_fallback_reason` usa `status_code` del error si existe y busca `429`/`413` como palabra completa.

## Alternativas consideradas

- **Seguir con `deepseek-chat`** — funciona hoy, pero depende de un alias no documentado.
- **Razonamiento activado con JSON mode** (`response_format: json_object` + validación Pydantic) — más código, la
  documentación no confirma que el modo razonamiento lo acepte, y el razonamiento aporta poco: el cálculo es
  determinístico y el reporte es redacción anclada (ADR-0019). Queda como experimento posible con `tests/eval_runner.py`.

## Consecuencias

- DeepSeek funciona sin configuración extra más allá de la URL, la key y el modelo; `deepseek-v4-pro` también.
- `LLM_THINKING=enabled` reproduce el error documentado: solo tiene sentido si se cambia el método de salida estructurada.
- Si otro proveedor compatible incorpora un parámetro similar, se configura con `LLM_THINKING`.
