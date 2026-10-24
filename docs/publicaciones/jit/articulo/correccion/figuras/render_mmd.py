import sys, html
from playwright.sync_api import sync_playwright
src = open(sys.argv[1]).read()
page_html = f"""<html><body style='margin:0;background:white'>
<pre class='mermaid'>{html.escape(src)}</pre>
<script src='https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js'></script>
<script>mermaid.initialize({{startOnLoad:true, theme:'default', fontFamily:'Arial'}});</script></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/home/marcosdebona/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell")
    pg = b.new_page(device_scale_factor=4)
    pg.set_content(page_html); pg.wait_for_selector("pre.mermaid svg", timeout=30000)
    pg.locator("pre.mermaid svg").screenshot(path=sys.argv[2])
    b.close()
