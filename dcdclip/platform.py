"""Pick the host backends for the current platform."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dcdclip.keyboard.backend import KeyboardBackend
from dcdclip.windows.base import WindowBackend


@dataclass
class Backends:
    windows: WindowBackend
    keyboard: KeyboardBackend
    hotkeys: object | None  # X11Hotkeys or None when unsupported

    def close(self) -> None:
        for b in (self.hotkeys, self.keyboard, self.windows):
            if b is not None:
                try:
                    b.close()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001
                    pass


def create_backends() -> Backends:
    if sys.platform.startswith("linux"):
        if os.environ.get("XDG_SESSION_TYPE") == "wayland" and not os.environ.get("DISPLAY"):
            raise RuntimeError(
                "Wayland session without an X display. Only X11 is supported so far; "
                "log in to an X11 session or run under XWayland with DISPLAY set."
            )
        from dcdclip.keyboard.backend_x11 import X11Keyboard
        from dcdclip.windows.hotkeys_x11 import X11Hotkeys
        from dcdclip.windows.x11 import X11Windows

        return Backends(windows=X11Windows(), keyboard=X11Keyboard(), hotkeys=X11Hotkeys())
    raise RuntimeError(
        f"platform {sys.platform!r} is not supported yet (planned: macOS via Quartz, "
        "Windows via SendInput)."
    )
