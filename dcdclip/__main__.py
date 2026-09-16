"""Entry point: ``python -m dcdclip`` or the ``dcdclip`` console script."""

from __future__ import annotations

import sys

from dcdclip import __version__


def main() -> int:
    if any(arg in ("--version", "-V") for arg in sys.argv[1:]):
        print(f"dcdclip {__version__}")
        return 0
    from dcdclip.gui.app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
