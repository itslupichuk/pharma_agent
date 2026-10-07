"""Entry point for the packaged RXTERM desktop app (PyInstaller).

Double-clicking RXTERM.exe opens the terminal. On Windows it relaunches itself inside
Windows Terminal when available (true colour, Unicode charts, resizable), otherwise it
sizes the classic console. Any arguments are passed straight to the `rxterm` CLI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _windows_launch() -> bool:
    """Return True if we handed off to Windows Terminal and this process should exit."""
    if os.environ.get("WT_SESSION") or os.environ.get("RXTERM_NO_WT"):
        return False
    wt = shutil.which("wt.exe") or shutil.which("wt")
    if not wt:
        return False
    try:
        subprocess.Popen([wt, "--size", "200,56", "new-tab", "--title", "RXTERM", "--suppressApplicationTitle",
                          sys.executable], close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return True
    except OSError:
        return False


def main() -> int:
    interactive = len(sys.argv) == 1
    if sys.platform == "win32":
        if interactive and getattr(sys, "frozen", False) and _windows_launch():
            return 0
        os.environ.setdefault("PYTHONUTF8", "1")
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleTitleW("RXTERM")
            if interactive and not os.environ.get("WT_SESSION"):
                os.system("mode con: cols=200 lines=56 >nul 2>&1")
        except Exception:
            pass

    from rxterm.cli import main as cli_main

    try:
        return cli_main()
    except Exception as exc:  # keep the window open so the error is readable
        import traceback

        traceback.print_exc()
        if interactive:
            input(f"\nRXTERM hit an error: {exc}\nPress Enter to close…")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
