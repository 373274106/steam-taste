"""Screenshot the Result page (demo user) across all 3 tabs + states."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)


def shoot(page, name: str):
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / f"result_{name}.png"), full_page=True)
    print(f"saved result_{name}.png")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for vp_name, w, h in [("desktop", 1440, 900), ("mobile", 390, 844)]:
        ctx = browser.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=2
        )
        page = ctx.new_page()

        # Loading state — hard to capture reliably, so visit and screenshot fast
        page.goto("http://localhost:5173/result?steamid=-1&demo=1", wait_until="domcontentloaded")
        page.wait_for_timeout(200)
        try:
            page.screenshot(path=str(OUT / f"result_loading_{vp_name}.png"), full_page=True)
            print(f"saved result_loading_{vp_name}.png (best-effort)")
        except Exception:
            pass

        # Wait for taste tab to fully load
        page.wait_for_selector("text=act i", timeout=20000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        shoot(page, f"taste_{vp_name}")

        # Click ACT II
        page.locator("button:has-text('what you')").first.click()
        page.wait_for_timeout(700)
        shoot(page, f"recs_{vp_name}")

        # Click ACT III
        page.locator("button:has-text('quietly')").first.click()
        page.wait_for_timeout(700)
        shoot(page, f"regret_{vp_name}")

        ctx.close()

    # Error state via bogus SteamID
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto("http://localhost:5173/result?steamid=76561199999999999", wait_until="networkidle")
    page.wait_for_timeout(2000)
    shoot(page, "error_desktop")
    ctx.close()

    browser.close()
print("done")
