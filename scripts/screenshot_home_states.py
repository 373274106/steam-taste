"""Capture Home in error state + check loading button visually."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
    page = ctx.new_page()

    # Error state via query param
    page.goto("http://localhost:5173/?error=auth_failed", wait_until="networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / "home_error_state.png"), full_page=True)
    print("saved home_error_state.png")

    # Filled-input state (hovering over button)
    page.goto("http://localhost:5173", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.fill('#sid', "https://steamcommunity.com/id/hexquarter")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "home_filled_input.png"), full_page=True)
    print("saved home_filled_input.png")

    # Hover state on entry option 01
    page.goto("http://localhost:5173", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.hover('text=sign in with steam')
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / "home_hover_01.png"), full_page=True)
    print("saved home_hover_01.png")

    ctx.close()
    browser.close()
print("done")
