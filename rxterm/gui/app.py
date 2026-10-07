"""Open RXTERM in its own desktop window (no console).

Order of preference:
  1. a native window via pywebview (Microsoft Edge WebView2 on Windows),
  2. Microsoft Edge / Chrome in "app" mode (a chromeless window),
  3. the default browser.
The app keeps running until its window is closed.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..config import Settings
from .backend import Backend
from .server import Server

log = logging.getLogger(__name__)


def _quiet_std_streams() -> None:
    """A windowed .exe has no stdout/stderr; give libraries somewhere harmless to write."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _log_to_file(cfg: Settings) -> Path:
    path = cfg.home / "rxterm.log"
    try:
        if path.exists() and path.stat().st_size > 2_000_000:
            path.unlink()
    except OSError:
        pass
    h = logging.FileHandler(path, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(h)
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    for noisy in ("yfinance", "urllib3", "httpx", "peewee", "pywebview"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return path


def fatal(msg: str) -> None:
    log.error(msg)
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, msg, "RXTERM", 0x10)
            return
        except Exception:
            pass
    print(msg, file=sys.stderr)


def _icon() -> str | None:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    for p in (base / "assets" / "rxterm.ico", Path(__file__).with_name("static") / "icon.png"):
        if p.exists():
            return str(p)
    return None


def _webview(url: str, cfg: Settings) -> bool:
    try:
        import webview
    except Exception as exc:  # not installed / no backend on this machine
        log.info("pywebview unavailable: %s", exc)
        return False
    try:
        webview.create_window("RXTERM — Pharma & Biotech Terminal", url, width=1500, height=920, min_size=(1000, 640),
                              maximized=True, background_color="#000000", text_select=False)
        kw = {"private_mode": False, "storage_path": str(cfg.home / "window")}
        if sys.platform == "win32":
            kw["gui"] = "edgechromium"
        ico = _icon()
        try:
            webview.start(icon=ico, **kw) if ico else webview.start(**kw)
        except TypeError:  # older pywebview without icon/private_mode
            webview.start(**({"gui": kw["gui"]} if "gui" in kw else {}))
        return True
    except Exception as exc:
        log.exception("pywebview failed: %s", exc)
        return False


def _find_browser_app() -> str | None:
    cands = [shutil.which(x) for x in ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser")]
    if sys.platform == "win32":
        for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            root = os.environ.get(env)
            if root:
                cands += [str(Path(root) / "Microsoft/Edge/Application/msedge.exe"),
                          str(Path(root) / "Google/Chrome/Application/chrome.exe")]
    elif sys.platform == "darwin":
        cands += ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((c for c in cands if c and Path(c).exists()), None)


def _app_window(url: str, cfg: Settings) -> bool:
    exe = _find_browser_app()
    if not exe:
        return False
    profile = cfg.home / "window-browser"
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    try:
        p = subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profile}", "--start-maximized",
                              "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"],
                             creationflags=flags)
    except OSError as exc:
        log.info("app-mode browser failed: %s", exc)
        return False
    p.wait()  # a dedicated profile means this process lives exactly as long as the window
    return True


def _browser(url: str, backend: Backend) -> None:
    import webbrowser

    webbrowser.open(url)
    backend.last_seen = time.time()
    while time.time() - backend.last_seen < 45:  # the page polls every 3 s; stop once it's gone
        time.sleep(3)


def run(cfg: Settings, mode: str = "auto") -> int:
    _quiet_std_streams()
    cfg.ensure_home()
    logfile = _log_to_file(cfg)
    try:
        backend = Backend(cfg)
        backend.start()
        server = Server(backend)
        server.start()
    except Exception as exc:
        log.exception("startup failed")
        fatal(f"RXTERM could not start:\n\n{exc}\n\nDetails are in {logfile}")
        return 1
    url = server.url
    log.info("RXTERM window at %s (mode=%s)", url.split("?")[0], mode)
    try:
        if mode in ("auto", "window") and _webview(url, cfg):
            pass
        elif mode in ("auto", "app") and _app_window(url, cfg):
            pass
        else:
            _browser(url, backend)
    finally:
        try:
            backend.shutdown()
        except Exception:
            log.exception("shutdown")
        server.stop()
    return 0
