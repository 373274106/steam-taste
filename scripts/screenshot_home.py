"""Take screenshots of Home page at multiple viewports for visual review."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)

viewports = [
    ("desktop_1440", 1440, 900),
    ("laptop_1280", 1280, 800),
    ("mobile_390", 390, 844),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, w, h in viewports:
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto("http://localhost:5173", wait_until="networkidle")
        page.wait_for_timeout(800)  # let fonts finish swapping
        page.screenshot(path=str(OUT / f"home_{name}.png"), full_page=True)
        print(f"saved home_{name}.png ({w}x{h})")
        ctx.close()
    browser.close()
print("done")
