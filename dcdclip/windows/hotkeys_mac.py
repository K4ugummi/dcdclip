"""Global hotkeys on macOS via a listen-only ``CGEventTap`` (needs Accessibility)."""

from __future__ import annotations

import threading
from collections.abc import Callable

import Quartz

from dcdclip.keyboard.keycodes_mac import MAC_KEYCODES, code_for_hotkey_name
from dcdclip.windows.hotkey_spec import parse_hotkey_spec

_MOD_FLAGS = {
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "shift": Quartz.kCGEventFlagMaskShift,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "super": Quartz.kCGEventFlagMaskCommand,
}
_ALL_MODS = sum(_MOD_FLAGS.values())


class MacHotkeys:
    def __init__(self) -> None:
        self._bindings: dict[tuple[int, int], Callable[[], None]] = {}
        self._thread: threading.Thread | None = None
        self._loop = None
        self._tap = None
        self._error: str | None = None

    def bind(self, spec: str, callback: Callable[[], None]) -> None:
        parsed = parse_hotkey_spec(spec)
        flags = sum(_MOD_FLAGS[m] for m in parsed.mods)
        keycode = MAC_KEYCODES[code_for_hotkey_name(parsed.key)]
        self._bindings[(keycode, flags)] = callback

    def unbind_all(self) -> None:
        self._bindings.clear()

    def start(self) -> None:
        if self._thread is not None:
            if self._error:
                raise RuntimeError(self._error)
            return
        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(ready,), name="mac-hotkeys", daemon=True
        )
        self._thread.start()
        ready.wait(2)
        if self._error:
            raise RuntimeError(self._error)

    def _callback(self, _proxy, etype, event, _refcon):
        if etype == Quartz.kCGEventTapDisabledByTimeout and self._tap is not None:
            Quartz.CGEventTapEnable(self._tap, True)
            return event
        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event) & _ALL_MODS
        cb = self._bindings.get((int(keycode), int(flags)))
        if cb:
            cb()
        return event

    def _run(self, ready: threading.Event) -> None:
        mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self._callback,
            None,
        )
        if self._tap is None:
            self._error = (
                "cannot install the keyboard event tap; grant dcdclip the Accessibility "
                "permission in System Settings > Privacy & Security"
            )
            ready.set()
            return
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        ready.set()
        Quartz.CFRunLoopRun()

    def close(self) -> None:
        self._bindings.clear()
        if self._loop is not None:
            Quartz.CFRunLoopStop(self._loop)
        if self._thread is not None:
            self._thread.join(2)
            self._thread = None
