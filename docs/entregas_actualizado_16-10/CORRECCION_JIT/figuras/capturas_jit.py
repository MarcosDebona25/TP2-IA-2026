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
    dd = page.get_by_label("Paciente", exact=True)
    dd.click(); page.wait_for_timeout(300)
    page.get_by_role("option", name="P003").first.click(); page.wait_for_timeout(800)
    # Fig. 2: barra de consulta + perfil del paciente
    toolbar = page.locator(".tp2-toolbar").first
    profile = page.locator(".tp2-profile").first
    tb, pb = toolbar.bounding_box(), profile.bounding_box()
    page.screenshot(path=str(OUT / "fig2_consulta.png"),
                    clip={"x": tb["x"] - 4, "y": tb["y"] - 4, "width": tb["width"] + 8,
                          "height": pb["y"] + pb["height"] - tb["y"] + 8})
    page.get_by_role("button", name="Analizar paciente").click()
    page.wait_for_timeout(1500)
    for _ in range(120):
        if not page.locator(".progress-text, .generating").count():
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2000)
    acc = page.locator(".block", has_text="Alertas detectadas").filter(has=page.locator("table")).last
    acc.screenshot(path=str(OUT / "fig3_alertas.png"))
    page.screenshot(path=str(OUT / "full_p003.png"), full_page=True)
    b.close()
print("ok")
