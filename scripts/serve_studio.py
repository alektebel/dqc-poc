#!/usr/bin/env python3
"""Serve the DQC Studio (static SPA) and proxy /api/* to the FastAPI backend.

Local dev without Docker/npm/nginx:

    python scripts/serve_studio.py                 # :4200, backend on :8000
    python scripts/serve_studio.py --port 4200 --backend http://localhost:8000

The studio app calls `/api/dqc/...`; this server forwards `/api/*` to the
backend (stripping the `/api` prefix) and serves the static files from
DQC/studio. CORS isn't needed because the browser only ever talks to :4200.
"""

from __future__ import annotations

import argparse
import http.server
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / "DQC" / "studio"


class StudioHandler(http.server.SimpleHTTPRequestHandler):
    backend = "http://localhost:8000"

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        return self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        return self.send_error(405)

    def _proxy(self):
        target = self.backend.rstrip("/") + self.path[4:]
        body = None
        if self.command in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
        req = urllib.request.Request(
            target,
            data=body,
            method=self.command,
            headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("content-length", "transfer-encoding", "connection"):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:  # noqa: BLE001
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"detail":"{e}"}}'.encode())

    def log_message(self, fmt, *args):  # keep logs quiet
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=4200)
    ap.add_argument("--backend", default="http://localhost:8000")
    args = ap.parse_args()

    os_chdir = __import__("os").chdir
    os_chdir(STUDIO)
    handler = type("Handler", (StudioHandler,), {"backend": args.backend})
    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"DQC Studio → http://localhost:{args.port}  (backend {args.backend})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
