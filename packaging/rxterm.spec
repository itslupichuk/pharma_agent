# PyInstaller spec for the RXTERM desktop app.   pyinstaller packaging/rxterm.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "rxterm" / "tui" / "rxterm.tcss"), "rxterm/tui"),
    (str(ROOT / "rxterm" / "brief" / "templates"), "rxterm/brief/templates"),
    (str(ROOT / "config" / "catalysts.yaml"), "config"),
    (str(ROOT / ".env.example"), "."),
    (str(ROOT / "docs" / "USER_GUIDE.md"), "docs"),
]
binaries = []
hiddenimports = collect_submodules("rxterm") + collect_submodules("rich")
for pkg in ("textual", "yfinance", "curl_cffi", "tzdata", "feedparser", "certifi"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "rxterm_app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = ROOT / "assets" / "rxterm.ico"
exe = EXE(
    pyz,
    a.scripts,
    [("X utf8_mode=1", None, "OPTION")],  # UTF-8 everywhere, regardless of the Windows code page
    exclude_binaries=True,
    name="RXTERM",
    console=True,
    icon=str(icon) if icon.exists() else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RXTERM")
