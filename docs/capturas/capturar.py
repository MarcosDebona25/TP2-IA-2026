"""Capturas de la UI Gradio para la documentación (Playwright headless, página completa, escala 2).

Requiere la app levantada (uv run python main.py) con el LLM activo en .env.
Uso: uv run --no-project --with playwright python docs/capturas/capturar.py docs/capturas
Si el Clínico cae al respaldo determinístico, el análisis se repite (hasta 3 intentos);
si sigue degradado, la captura de ese paciente se omite.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7860"
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT.mkdir(parents=True, exist_ok=True)
PACIENTES = ["P001", "P002", "P003", "P004", "P005"]


def shot(page, name):
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print("OK", name)


def wait_idle(page, max_s=120):
    page.wait_for_timeout(2000)
    for _ in range(max_s):
        if not page.locator(".progress-text, .generating, .eta-bar, .pending").count():
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2000)


def degraded(page) -> bool:
    body = page.inner_text("body")
    return "Probá de nuevo" in body or "determinístico" in body.split("Herramienta de soporte")[1]


def pick_patient(page, pid):
    page.locator(".tp2-sidebar input").first.click()
    page.wait_for_timeout(400)
    page.get_by_role("option", name=pid, exact=False).first.click()
    page.wait_for_timeout(1500)


def analyze(page, pid) -> bool:
    for _ in range(3):
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(2500)
        pick_patient(page, pid)
        page.get_by_role("button", name="Analizar paciente").click()
        wait_idle(page)
        if not degraded(page):
            return True
        print("Análisis degradado, se repite", pid)
    return False


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(
        viewport={"width": 1600, "height": 1000}, device_scale_factor=2, color_scheme="light"
    ).new_page()
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_timeout(2500)
    shot(page, "00-inicio")

    omitidos = []
    for pid in PACIENTES:
        if analyze(page, pid):
            shot(page, f"01-consulta-{pid}")
        else:
            omitidos.append(pid)

    # Chat de seguimiento sobre el reporte de P003
    if analyze(page, "P003"):
        chat = page.get_by_placeholder("Escribí una pregunta…")
        chat.fill("¿Qué significa la HbA1c en este paciente?")
        chat.press("Enter")
        wait_idle(page)
        shot(page, "02-chat-seguimiento")
    else:
        omitidos.append("chat")

    page.get_by_role("tab", name="Observabilidad").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Refrescar").first.click()
    page.wait_for_timeout(2500)
    shot(page, "03-observabilidad")

    page.get_by_role("tab", name="Evaluación").click()
    page.wait_for_timeout(2500)
    shot(page, "04-evaluacion")
    browser.close()

if omitidos:
    sys.exit(f"Capturas omitidas por análisis degradado: {', '.join(omitidos)}")
