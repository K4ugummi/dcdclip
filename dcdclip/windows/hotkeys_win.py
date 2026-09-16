"""Global hotkeys on Windows via ``RegisterHotKey`` in a message-loop thread."""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from dcdclip.keyboard.keycodes_win import VK
from dcdclip.windows.hotkey_spec import parse_hotkey_spec

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_MOD_FLAGS = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT, "super": MOD_WIN}


def vk_for_key(name: str) -> int:
    name = name.lower()
    if name in VK:
        return VK[name]
    if len(name) == 1:
        # VkKeyScanW maps a character to a virtual key for the current layout.
        user32 = ctypes.WinDLL("user32")
        res = user32.VkKeyScanW(ctypes.c_wchar(name))
        if res == -1:
            raise ValueError(f"no virtual key for {name!r}")
        return res & 0xFF
    raise ValueError(f"unknown hotkey key {name!r}")


class WinHotkeys:
    def __init__(self) -> None:
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._bindings: list[tuple[int, int, Callable[[], None]]] = []  # (mods, vk, cb)
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._errors: list[str] = []

    def bind(self, spec: str, callback: Callable[[], None]) -> None:
        parsed = parse_hotkey_spec(spec)
        mods = sum(_MOD_FLAGS[m] for m in parsed.mods) | MOD_NOREPEAT
        self._bindings.append((mods, vk_for_key(parsed.key), callback))

    def unbind_all(self) -> None:
        self.stop()
        self._bindings.clear()

    def start(self) -> None:
        if self._thread is not None or not self._bindings:
            return
        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, args=(ready,), name="win-hotkeys", daemon=True
        )
        self._thread.start()
        ready.wait(2)
        if self._errors:
            errors, self._errors = self._errors, []
            raise RuntimeError("; ".join(errors))

    def stop(self) -> None:
        if self._thread is None:
            return
        if self._thread_id is not None:
            self.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(2)
        self._thread = None
        self._thread_id = None

    def _loop(self, ready: threading.Event) -> None:
        u = self.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered: dict[int, Callable[[], None]] = {}
        for i, (mods, vk, cb) in enumerate(self._bindings, start=1):
            if u.RegisterHotKey(None, i, mods, vk):
                registered[i] = cb
            else:
                self._errors.append(
                    f"hotkey id {i} already in use (error {ctypes.get_last_error()})"
                )
        ready.set()
        msg = wintypes.MSG()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    cb = registered.get(int(msg.wParam))
                    if cb:
                        cb()
        finally:
            for i in registered:
                u.UnregisterHotKey(None, i)

    def close(self) -> None:
        self.stop()
