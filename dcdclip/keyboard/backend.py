"""Host keyboard backend interface."""

from __future__ import annotations

from typing import Protocol

from dcdclip.keyboard.planner import KeyTap


class KeyboardBackend(Protocol):
    """Sends key events to the host OS. Implementations: X11 (XTEST); planned: macOS, Windows."""

    name: str

    def tap(self, tap: KeyTap, hold_s: float) -> None:
        """Press modifiers, press the key, wait ``hold_s``, release everything."""

    def release_all(self) -> None:
        """Release any modifier that might still be held (called after abort/errors)."""

    def close(self) -> None: ...
