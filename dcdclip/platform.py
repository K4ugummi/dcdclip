"""Pick the host backends for the current platform."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from dcdclip.keyboard.backend import KeyboardBackend
from dcdclip.windows.base import WindowBackend


@dataclass
class Backends:
    windows: WindowBackend
    keyboard: KeyboardBackend
    hotkeys: object | None  # platform hotkey listener or None when unsupported
    notes: list[str] = field(default_factory=list)  # warnings to show the user at start

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
                "Wayland session without an X display. Only X11 is supported on Linux; "
                "log in to an X11 session or run under XWayland with DISPLAY set."
            )
        from dcdclip.keyboard.backend_x11 import X11Keyboard
        from dcdclip.windows.hotkeys_x11 import X11Hotkeys
        from dcdclip.windows.x11 import X11Windows

        return Backends(windows=X11Windows(), keyboard=X11Keyboard(), hotkeys=X11Hotkeys())

    if sys.platform == "win32":
        from dcdclip.keyboard.backend_win import WinKeyboard
        from dcdclip.windows.hotkeys_win import WinHotkeys
        from dcdclip.windows.win32 import Win32Windows

        return Backends(windows=Win32Windows(), keyboard=WinKeyboard(), hotkeys=WinHotkeys())

    if sys.platform == "darwin":
        from dcdclip.keyboard.backend_mac import MacKeyboard, accessibility_trusted
        from dcdclip.windows.hotkeys_mac import MacHotkeys
        from dcdclip.windows.macos import MacWindows

        notes = []
        if not accessibility_trusted():
            notes.append(
                "macOS: Accessibility permission not granted. Typing and hotkeys will not "
                "work until dcdclip is allowed under System Settings > Privacy & Security > "
                "Accessibility (and Screen Recording for window titles and OCR captures)."
            )
        return Backends(
            windows=MacWindows(), keyboard=MacKeyboard(), hotkeys=MacHotkeys(), notes=notes
        )

    raise RuntimeError(f"platform {sys.platform!r} is not supported.")
