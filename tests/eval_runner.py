# tests/eval_runner.py
#
# Evaluación CUALITATIVA del sistema de agentes (ver docs/tests.md). NO es un test de
# pytest: corre los casos de tests/cases/*.json contra el grafo con LLM real y vuelca un
# artefacto Markdown (esperado vs. obtenido) para que un humano puntúe el desempeño.
# El día de mañana, ese juicio manual lo reemplaza un LLM-as-judge.
#
# Uso:  uv run python tests/eval_runner.py [salida.md]   (default: logs/eval_report.md)

import json
import sys
from datetime import datetime
from pathlib import Path

# Permite ejecutarlo como script suelto (sin -m) resolviendo la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from agents.llm_factory import has_api_key
from orchestrator.graph import build_graph

load_dotenv()

CASES_DIR = Path(__file__).parent / "cases"
CATEGORIES = ["happy_path", "edge_cases", "adversarial"]


def _load_all_cases() -> list[dict]:
    cases = []
    for category in CATEGORIES:
        cases.extend(json.loads((CASES_DIR / f"{category}.json").read_text(encoding="utf-8")))
    return cases


def _run_case(case: dict) -> str:
    """Corre setup + input sobre un thread aislado y devuelve el reporte final."""
    app = build_graph()
    cfg = {"configurable": {"thread_id": f"eval-{case['id']}"}}

    invocations = list(case.get("setup", [])) + [case["input"]]
    invocations[0] = {"conversation": [], **invocations[0]}

    final = None
    for payload in invocations:
        final = app.invoke(payload, cfg)
    return final.get("report") or "(sin reporte)"


def _render(case: dict, obtained: str) -> str:
    inp = case["input"]
    setup_note = f"\n**Setup previo:** {case['setup']}" if case.get("setup") else ""
    return (
        f"## {case['id']} — {case['category']}\n\n"
        f"**Descripción:** {case['description']}{setup_note}\n\n"
        f"**Input:** `{inp}`\n\n"
        f"**Comportamiento esperado:** {case['expected_behavior']}\n\n"
        f"**Salida obtenida:**\n\n```\n{obtained}\n```\n\n"
        f"**Puntuación (manual, 1-5):** ___\n\n"
        f"**Notas:** \n\n---\n"
    )


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("logs/eval_report.md")

    if not has_api_key():
        print("⚠️  No hay API key: el grafo correría en fallback determinístico y la "
              "evaluación cualitativa no tendría sentido. Configurá GROQ_API_KEY/GOOGLE_API_KEY.")
        sys.exit(1)

    cases = _load_all_cases()
    print(f"Evaluando {len(cases)} casos con LLM real…")

    blocks = [
        f"# Reporte de evaluación cualitativa\n\n"
        f"Generado: {datetime.now().isoformat(timespec='seconds')} · {len(cases)} casos\n\n"
        f"Puntuar cada caso comparando *esperado* vs. *obtenido*. Ver docs/tests.md.\n\n---\n"
    ]
    for case in cases:
        print(f"  · {case['id']}…")
        try:
            obtained = _run_case(case)
        except Exception as e:  # un caso roto no debe frenar la evaluación completa
            obtained = f"(ERROR: {type(e).__name__}: {e})"
        blocks.append(_render(case, obtained))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    print(f"✅ Artefacto escrito en {out_path}")


if __name__ == "__main__":
    main()
