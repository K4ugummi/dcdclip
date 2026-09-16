"""Entry point: ``python -m dcdclip`` or the ``dcdclip`` console script."""

from __future__ import annotations

import sys

from dcdclip import __version__


def check() -> int:
    """Print backend diagnostics without starting the GUI or sending any key."""
    from dcdclip.platform import create_backends

    print(f"dcdclip {__version__} on {sys.platform}")
    b = create_backends()
    try:
        print(f"window backend:   {b.windows.name}")
        print(f"keyboard backend: {b.keyboard.name}")
        print(f"hotkey backend:   {type(b.hotkeys).__name__ if b.hotkeys else 'none'}")
        for note in b.notes:
            print(f"note: {note}")
        wins = b.windows.list_windows()
        active = b.windows.active_window_id()
        print(f"windows: {len(wins)} (active id: {active})")
        for w in wins[:8]:
            geo = b.windows.geometry(w.id)
            print(f"  {w.id:>10}  {w.label()[:60]!r}  {geo}")
    finally:
        b.close()
    return 0


def main() -> int:
    args = sys.argv[1:]
    if any(arg in ("--version", "-V") for arg in args):
        print(f"dcdclip {__version__}")
        return 0
    if "--check" in args:
        return check()
    from dcdclip.gui.app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
