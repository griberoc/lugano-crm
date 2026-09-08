"""Local-only frontend preview. Uses the real local API; never supplies demo data."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/config.js":
            config = (ROOT / "frontend/config.js").read_text(encoding="utf-8")
            config += '\nwindow.LUGANO_CONFIG.apiBaseUrl = "http://127.0.0.1:8000";\n'
            config += 'window.LUGANO_CONFIG.adminApiBaseUrl = "http://127.0.0.1:8000";\n'
            config += 'window.LUGANO_CONFIG.previewReadOnly = true;\n'
            payload = config.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    handler = partial(PreviewHandler, directory=str(ROOT / "frontend"))
    print("Lugano local: http://127.0.0.1:5176/orders/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 5176), handler).serve_forever()
