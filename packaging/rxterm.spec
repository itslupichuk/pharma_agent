# PyInstaller spec for the RXTERM desktop app.   pyinstaller packaging/rxterm.spec --noconfirm
#
# Two programs share one folder:
#   RXTERM.exe      the app: opens the RXTERM window, no console (this is what the shortcuts start)
#   rxterm-cli.exe  the same code with a console, for the command line (brief, selftest, terminal, ...)
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "rxterm" / "tui" / "rxterm.tcss"), "rxterm/tui"),
    (str(ROOT / "rxterm" / "brief" / "templates"), "rxterm/brief/templates"),
    (str(ROOT / "rxterm" / "gui" / "static"), "rxterm/gui/static"),
    (str(ROOT / "assets" / "rxterm.ico"), "assets"),
    (str(ROOT / "config" / "catalysts.yaml"), "config"),
    (str(ROOT / ".env.example"), "."),
    (str(ROOT / "docs" / "USER_GUIDE.md"), "docs"),
]
binaries = []
hiddenimports = collect_submodules("rxterm") + collect_submodules("rich")
pkgs = ["textual", "yfinance", "curl_cffi", "tzdata", "feedparser", "certifi"]
try:  # the native window (Windows: pywebview + pythonnet -> Edge WebView2)
    import webview  # noqa: F401

    pkgs += ["webview", "clr_loader", "pythonnet", "proxy_tools", "bottle"]
    hiddenimports += ["clr", "webview.platforms.edgechromium", "webview.platforms.winforms"]
except ImportError:
    pass
for pkg in pkgs:
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "rxterm_app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PySide6", "PyQt6", "gi"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = ROOT / "assets" / "rxterm.ico"
opts = [("X utf8_mode=1", None, "OPTION")]  # UTF-8 everywhere, regardless of the Windows code page
app = EXE(pyz, a.scripts, opts, exclude_binaries=True, name="RXTERM", console=False,
          icon=str(icon) if icon.exists() else None, upx=False)
cli = EXE(pyz, a.scripts, opts, exclude_binaries=True, name="rxterm-cli", console=True,
          icon=str(icon) if icon.exists() else None, upx=False)
coll = COLLECT(app, cli, a.binaries, a.datas, strip=False, upx=False, name="RXTERM")
