"""Global hotkeys on X11 via XGrabKey, running in a background thread."""

from __future__ import annotations

import threading
from collections.abc import Callable

from Xlib import XK, X, display

_MOD_MASKS = {
    "ctrl": X.ControlMask,
    "control": X.ControlMask,
    "shift": X.ShiftMask,
    "alt": X.Mod1Mask,
    "super": X.Mod4Mask,
    "win": X.Mod4Mask,
    "meta": X.Mod4Mask,
}
_IGNORED_MASKS = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask)  # CapsLock, NumLock


def parse_hotkey(spec: str) -> tuple[int, str]:
    """``"ctrl+alt+v"`` -> (modifier mask, keysym name)."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    mask = 0
    for part in parts[:-1]:
        try:
            mask |= _MOD_MASKS[part]
        except KeyError as exc:
            raise ValueError(f"unknown modifier {part!r} in hotkey {spec!r}") from exc
    return mask, parts[-1]


class X11Hotkeys:
    """Register ``spec -> callback`` pairs; callbacks run on the listener thread."""

    def __init__(self) -> None:
        self.display = display.Display()
        self.errors: list[str] = []
        self.display.set_error_handler(self._on_error)
        self.root = self.display.screen().root
        self._bindings: dict[tuple[int, int], Callable[[], None]] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def _on_error(self, err, _request) -> None:
        # BadAccess = another client (e.g. a second dcdclip instance) already grabbed the key.
        self.errors.append(type(err).__name__)

    def bind(self, spec: str, callback: Callable[[], None]) -> None:
        mask, keyname = parse_hotkey(spec)
        keysym = XK.string_to_keysym(keyname)
        if keysym == 0:
            raise ValueError(f"unknown key {keyname!r} in hotkey {spec!r}")
        keycode = self.display.keysym_to_keycode(keysym)
        if keycode == 0:
            raise ValueError(f"key {keyname!r} not on the host keyboard")
        for extra in _IGNORED_MASKS:
            self.root.grab_key(keycode, mask | extra, True, X.GrabModeAsync, X.GrabModeAsync)
        self._bindings[(keycode, mask)] = callback
        self.errors.clear()
        self.display.sync()
        if self.errors:
            raise RuntimeError(f"hotkey {spec!r} is already grabbed by another application")

    def unbind_all(self) -> None:
        for keycode, mask in self._bindings:
            for extra in _IGNORED_MASKS:
                self.root.ungrab_key(keycode, mask | extra)
        self._bindings.clear()
        self.display.flush()

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="x11-hotkeys", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        clean = ~(X.LockMask | X.Mod2Mask)
        while not self._stop.is_set():
            if self.display.pending_events() == 0:
                self._stop.wait(0.05)
                continue
            ev = self.display.next_event()
            if ev.type != X.KeyPress:
                continue
            cb = self._bindings.get((ev.detail, ev.state & clean & 0xFF))
            if cb:
                cb()

    def close(self) -> None:
        self._stop.set()
        try:
            self.unbind_all()
        finally:
            self.display.close()
