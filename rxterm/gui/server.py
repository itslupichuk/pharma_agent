"""Tiny local HTTP server: serves the window's HTML/JS and answers /api/<method> calls.

Bound to 127.0.0.1 only, with a per-launch token so other local pages can't call it.
"""

from __future__ import annotations

import json
import logging
import math
import mimetypes
import secrets
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .backend import Backend

log = logging.getLogger(__name__)
STATIC = Path(__file__).with_name("static")
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain", ".woff2": "font/woff2"}

# method name -> (callable on Backend, accepted params)
API = {
    "status": ("status", ()), "monitor": ("monitor", ()), "tape": ("tape", ()), "stock": ("stock", ("ticker",)),
    "stock_news": ("stock_news", ("ticker",)),
    "bars": ("bars", ("ticker", "tf")), "compare": ("compare", ("tickers", "tf")), "ideas": ("ideas", ()),
    "screens": ("screens", ()), "screen": ("screen", ("code",)), "calendar": ("calendar", ()),
    "news": ("news", ("ticker",)), "chain": ("chain", ("ticker", "expiry")), "watchlist": ("watchlist", ()),
    "search": ("search", ("q",)), "help": ("help", ()), "prefs": ("prefs", ()),
    "watch_toggle": ("watch_toggle", ("ticker",)), "alert_add": ("alert_add", ("ticker", "op", "level")),
    "alert_del": ("alert_del", ("index",)), "refresh": ("refresh_all", ()), "open_url": ("open_url", ("url",)),
    "copy": ("copy_text", ("text",)), "set_prefs": ("set_prefs", None),
}


def clean(o):
    """Make anything the backend returns JSON-safe (NaN -> null, dates -> ISO)."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if hasattr(o, "item"):  # numpy scalars
        try:
            return clean(o.item())
        except (ValueError, AttributeError):
            pass
    return o


class Server:
    def __init__(self, backend: Backend, port: int = 0):
        self.backend = backend
        self.token = secrets.token_urlsafe(16)
        handler = self._handler()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="http").start()

    def stop(self) -> None:
        self.httpd.shutdown()

    def call(self, method: str, params: dict):
        spec = API.get(method)
        if spec is None:
            raise KeyError(method)
        fn = getattr(self.backend, spec[0])
        kwargs = params if spec[1] is None else {k: params[k] for k in spec[1] if k in params}
        return clean(fn(**kwargs))

    def _handler(self):
        srv = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "RXTERM"

            def log_message(self, fmt, *args):  # keep quiet
                log.debug("http " + fmt, *args)

            def _send(self, code: int, body: bytes, ctype: str, cache: bool = False) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _api(self, method: str, params: dict) -> None:
                if self.headers.get("X-RX-Token") != srv.token:
                    return self._send(403, b'{"error":"forbidden"}', "application/json")
                try:
                    out = srv.call(method, params)
                    body = json.dumps(out, separators=(",", ":"), allow_nan=False, default=str).encode()
                    self._send(200, body, "application/json")
                except KeyError:
                    self._send(404, b'{"error":"unknown method"}', "application/json")
                except Exception as exc:
                    log.exception("api %s failed", method)
                    self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")

            def do_GET(self):
                u = urlparse(self.path)
                if u.path.startswith("/api/"):
                    q = {k: v[0] for k, v in parse_qs(u.query).items()}
                    return self._api(u.path[5:], q)
                rel = u.path.lstrip("/") or "index.html"
                p = (STATIC / rel).resolve()
                if STATIC.resolve() not in p.parents or not p.is_file():
                    return self._send(404, b"not found", "text/plain")
                # explicit types: the Windows registry sometimes maps .js to text/plain
                ctype = TYPES.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype.endswith("javascript"):
                    ctype += "; charset=utf-8"
                self._send(200, p.read_bytes(), ctype, cache="vendor" in rel)

            def do_POST(self):
                u = urlparse(self.path)
                if not u.path.startswith("/api/"):
                    return self._send(404, b"not found", "text/plain")
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    params = json.loads(self.rfile.read(n) or b"{}") if n else {}
                except ValueError:
                    params = {}
                self._api(u.path[5:], params if isinstance(params, dict) else {})

        return Handler
