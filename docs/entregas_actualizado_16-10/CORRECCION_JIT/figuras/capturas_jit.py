"""Capturas recortadas para el artículo JIT: panel de consulta (Fig. 2) y alertas de P003 (Fig. 3)."""
import pathlib, sys
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
URL = "http://127.0.0.1:7860"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/home/marcosdebona/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell")
    page = b.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=2)
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_timeout(2000)
    dd = page.locator(".tp2-sidebar input").first
    dd.click(); page.wait_for_timeout(300)
    page.get_by_role("option", name="P003").first.click(); page.wait_for_timeout(800)
    # Fig. 2: barra lateral de consulta (ficha del paciente + contexto + acción)
    page.locator(".tp2-sidebar").first.screenshot(path=str(OUT / "fig2_consulta.png"))
    page.get_by_role("button", name="Analizar paciente").click()
    page.wait_for_timeout(1500)
    for _ in range(120):
        if not page.locator(".progress-text, .generating").count():
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2000)
    alerts = page.locator(".tp2-card").filter(
        has=page.get_by_role("heading", name="Alertas", exact=True)).filter(has=page.locator("table")).last
    alerts.screenshot(path=str(OUT / "fig3_alertas.png"))
    page.screenshot(path=str(OUT / "full_p003.png"), full_page=True)
    b.close()
print("ok")
