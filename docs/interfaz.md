# Interfaz de usuario (Gradio)

Interfaz web del sistema, construida con **Gradio**. Conecta al grafo real
([orchestrator/graph.py](../orchestrator/graph.py)); con `GROQ_API_KEY` usa los agentes ReAct,
y sin ella cae a los fallbacks determinísticos.

## Levantarla

```bash
uv run python -m interface.app   # http://127.0.0.1:7860
```

## Archivos

| Archivo | Rol |
|---|---|
| [interface/app.py](../interface/app.py) | Layout, pestañas y wiring de eventos. Invoca el grafo. |
| [interface/components.py](../interface/components.py) | Funciones **puras** de render (HTML/Markdown). Sin Gradio → testeables. |
| [interface/theme.py](../interface/theme.py) | Sistema visual: tema Gradio, tokens claro/oscuro, CSS, fuentes embebidas y selector de tema ([ADR-0021](adr/0021-sistema-visual-de-la-interfaz.md)). |
| [interface/assets/fonts/](../interface/assets/fonts/) | Plus Jakarta Sans y JetBrains Mono (OFL), embebidas → la UI funciona sin internet. |
| [interface/assets/logo.svg](../interface/assets/logo.svg) | Logo (monograma «MC» con línea de tendencia). Se usa como favicon; la barra superior usa el mismo glifo inline (`theme._ICON_LOGO`) en `currentColor` para que siga al selector de tema. |
| [interface/logging_config.py](../interface/logging_config.py) | Observabilidad (ver [docs/logs.md](logs.md)). |

## Sistema visual

- **Modo claro/oscuro**: botón (luna/sol) en la barra superior; la preferencia queda guardada en el
  navegador. Sin preferencia se usa la del sistema operativo. También sirve `?__theme=dark` en la URL.
- **Barra superior**: marca, estado del LLM (verde = LLM activo, ámbar = modo determinístico; el detalle
  completo aparece al pasar el mouse) y el aviso clínico permanente.
- **Colores**: siempre tokens `--tp-*` definidos para ambos modos en `theme.py`; nada de colores sueltos.
  La severidad se comunica con color **y** texto.
- Sin emojis decorativos en la UI.

## Pestaña 1 — Consulta

Sigue el flujo de la def. conceptual (§2.4). Barra lateral a la izquierda, área principal a la derecha:

1. **Seleccionar paciente** (desplegable). Los IDs salen de los CSV del EHR
   (`data/sample/*.csv`), de forma dinámica: al cambiar el fixture por el dataset real de B,
   el selector se actualiza solo.
2. **Ficha del paciente**: edad/sexo, diagnóstico, comorbilidades, sesiones previas, registros de EHR,
   último peso/PA y medicación activa.
3. **Contexto clínico adicional** (opcional): se pasa al estado como `doctor_context`.
4. **Analizar paciente**: ejecuta el pipeline Monitor → Clínico. Resultados:
   - **Indicadores** (franja superior): alertas por severidad, HbA1c, glucosa en ayunas y PA, con último
     valor y tendencia. Antes del análisis se ven vacíos («—»).
   - **Reporte clínico**, junto al chat de seguimiento.
   - **Alertas**: un renglón por grupo, con los mismos ids A1, A2… del reporte, peor valor, umbral y
     período. El detalle por registro está plegado («Ver los N registros fuera de meta»).
   - **Tendencias por métrica** (último, media, mín, máx, Δ, dirección).
5. **Seguimiento** (chat): preguntas sobre el reporte ya generado (van directo al Clínico).
   El Clínico responde **solo** dentro del dominio clínico del paciente; los pedidos ajenos
   (código, temas generales, etc.) se rechazan cortésmente.
6. **Guardar sesión**: envía la señal explícita `save_requested=True`. El nodo `save` del grafo
   persiste reporte, alertas y últimos valores de cada métrica en el historial, y el chat muestra el
   resultado real: el id de la sesión o el error. En el chat también sirven "confirmar" o
   "guardar sesión"; "sí" no guarda ([ADR-0008](adr/0008-guardado-explicito-de-sesion.md)).

## Pestaña 2 — Observabilidad

Visor del log estructurado (`logs/agent.jsonl`) para desarrollo, sin salir de la UI:

- Estado de **LangSmith** + enlace al dashboard.
- **Filtro** por tipo de evento (`node` / `routing` / `llm` / `tool`).
- Botón **Refrescar** (el log se llena al usar la pestaña de consulta).
- **JSON crudo** de la traza seleccionada al hacer clic en una fila.

Detalle de los campos y eventos del log: [docs/logs.md](logs.md).

## Datos de muestra

La UI y las tools del Monitor corren sobre el fixture [data/sample/](../data/sample/) (4 perfiles
`P001`–`P004`, ver su README). Es provisional: lo reemplaza el generador real de B al mismo schema
(contrato #1). El selector y el perfil degradan con elegancia si un paciente no tiene CSV.
