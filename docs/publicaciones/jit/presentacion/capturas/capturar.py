"""Capturas de la UI para la presentación JIT 2026 (Playwright headless, 1920x1080).

Requiere la app levantada (uv run python main.py) con el LLM activo en .env.
Uso: uv run --no-project --with playwright python docs/publicaciones/jit/presentacion/capturas/capturar.py docs/publicaciones/jit/presentacion/capturas
Si el Clínico cae al respaldo determinístico, el análisis se repite (hasta 3 intentos).
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7860"
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT.mkdir(parents=True, exist_ok=True)


def shot(page, name):
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / f"{name}.png"))
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


def scroll_to(page, js_find):
    y = page.evaluate(f"() => {{ const t = {js_find}; return t.getBoundingClientRect().top + window.scrollY - 60; }}")
    page.evaluate(f"window.scrollTo(0, {y})")


def analyze(page):
    page.get_by_role("button", name="Analizar paciente").click()
    wait_idle(page)
    return not degraded(page)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(viewport={"width": 1920, "height": 1080}, color_scheme="light").new_page()
    for attempt in range(3):
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(2500)
        shot(page, "01-inicio")
        page.locator(".tp2-sidebar input").first.click()
        page.wait_for_timeout(400)
        page.get_by_role("option", name="P003", exact=False).first.click()
        page.wait_for_timeout(1500)
        shot(page, "02-paciente-seleccionado")
        if analyze(page):
            break
        print("Análisis degradado, se repite")
    else:
        sys.exit("El Clínico cayó al respaldo en los 3 intentos: no se toman capturas del resultado")

    page.evaluate("window.scrollTo(0, 0)")
    shot(page, "03-reporte")
    scroll_to(page, "[...document.querySelectorAll('h3')].find(e => e.textContent.includes('Alertas y respaldo'))")
    shot(page, "04-reporte-guias")
    scroll_to(page, "[...document.querySelectorAll('.tp2-card-title')].find(e => e.textContent.trim() === 'Alertas')")
    shot(page, "05-alertas-tendencias")

    page.evaluate("window.scrollTo(0, 0)")
    chat = page.get_by_placeholder("Escribí una pregunta…")
    chat.fill("¿Qué significa la HbA1c en este paciente?")
    chat.press("Enter")
    wait_idle(page)
    page.evaluate("window.scrollTo(0, 0)")
    shot(page, "06-seguimiento")

    page.get_by_role("tab", name="Observabilidad").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Refrescar").first.click()
    page.wait_for_timeout(2500)
    shot(page, "07-observabilidad")
    browser.close()
