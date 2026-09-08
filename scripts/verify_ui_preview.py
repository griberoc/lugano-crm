"""Read-only browser smoke and throttled vitals against the real local preview."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ARTIFACTS = Path("test-results/ui-premium/real-preview")


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in [390, 360, 430, 768, 1440]:
            context = browser.new_context(
                viewport={"width": width, "height": 844}, locale="pt-BR"
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            # This script cannot submit orders, authenticate or change live records.
            page.route("**/*", lambda route: route.continue_()
                       if route.request.method in {"GET", "HEAD", "OPTIONS"}
                       else route.abort())
            cdp = context.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {
                "offline": False, "latency": 150,
                "downloadThroughput": 1_600_000 / 8,
                "uploadThroughput": 750_000 / 8,
                "connectionType": "cellular4g",
            })
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            page.goto("http://127.0.0.1:5176/orders/")
            page.locator("[data-add-product]").first.wait_for(timeout=30000)
            page.wait_for_timeout(1500)
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            result = page.evaluate("""() => ({
                width: innerWidth,
                products: document.querySelectorAll('[data-add-product]').length,
                vitals: window.__luganoVitals,
                firstProductTop: document.querySelector('.product-card').getBoundingClientRect().top,
                type: ['.hero-copy h1','.hero-copy p','.product-body p'].map(s=>{
                  const c=getComputedStyle(document.querySelector(s));
                  return {selector:s,family:c.fontFamily,size:c.fontSize};
                })
            })""")
            page.screenshot(path=str(ARTIFACTS / f"menu-{width}.png"))
            results.append(result)
            context.close()
        browser.close()
    (ARTIFACTS / "metrics.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
