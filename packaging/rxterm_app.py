"""Entry point for the packaged RXTERM app (PyInstaller).

RXTERM.exe (windowed) opens the RXTERM desktop window — no console.
rxterm-cli.exe (console) is the same program for the command line; any arguments go
straight to the `rxterm` CLI (brief, ideas, screen, selftest, terminal, ...).
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    windowed = sys.stdout is None
    if windowed:  # no console: give libraries a harmless place to print
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
        try:  # its own taskbar identity (icon/grouping) rather than "Python"
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RXTERM.App")
        except Exception:
            pass
        if not windowed:  # console build
            try:
                import ctypes

                ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            except Exception:
                pass

    from rxterm.cli import main as cli_main

    try:
        return cli_main()
    except Exception as exc:
        import traceback

        if windowed:  # show the problem instead of vanishing silently
            from rxterm.gui.app import fatal

            fatal(f"RXTERM hit an error:\n\n{exc}\n\n{traceback.format_exc()[-1500:]}")
        else:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
