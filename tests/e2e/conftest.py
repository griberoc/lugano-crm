from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return


@pytest.fixture(scope="session")
def frontend_url():
    handler = lambda *args, **kwargs: QuietStaticHandler(  # noqa: E731
        *args, directory=str(ROOT / "frontend"), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )
    page = context.new_page()
    page.on("pageerror", lambda error: print(f"Browser error: {error}"))
    try:
        yield page
    finally:
        context.close()
