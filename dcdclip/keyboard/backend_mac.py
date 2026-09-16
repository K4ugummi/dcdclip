"""macOS keyboard backend using Quartz ``CGEventPost`` (pyobjc).

Needs the Accessibility permission (System Settings > Privacy & Security > Accessibility)
for the running binary. Physical keys are posted as virtual key codes, keysyms as Unicode
strings on a keyboard event.
"""

from __future__ import annotations

import time

import Quartz

from dcdclip.keyboard.keycodes_mac import MAC_KEYCODES
from dcdclip.keyboard.model import CONTROL_KEYSYM_CODES, Mod, char_for_keysym
from dcdclip.keyboard.planner import KeyTap

NX_DEVICERALTKEYMASK = 0x00000040  # distinguishes the right Option key in the flags

MOD_CODES: dict[Mod, str] = {
    Mod.SHIFT: "ShiftLeft",
    Mod.ALTGR: "AltRight",
    Mod.CTRL: "ControlLeft",
    Mod.ALT: "AltLeft",
}
MOD_FLAGS: dict[Mod, int] = {
    Mod.SHIFT: Quartz.kCGEventFlagMaskShift,
    Mod.ALTGR: Quartz.kCGEventFlagMaskAlternate | NX_DEVICERALTKEYMASK,
    Mod.CTRL: Quartz.kCGEventFlagMaskControl,
    Mod.ALT: Quartz.kCGEventFlagMaskAlternate,
}


def accessibility_trusted() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False}))
    except Exception:  # noqa: BLE001
        return False


class MacKeyboard:
    name = "macos-quartz"

    def __init__(self) -> None:
        self._held: list[int] = []
        self._flags = 0

    def _post(self, keycode: int, down: bool, flags: int | None = None) -> None:
        ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        Quartz.CGEventSetFlags(ev, self._flags if flags is None else flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _press(self, code: str, mod: Mod | None = None) -> None:
        keycode = self._keycode(code)
        if mod is not None:
            self._flags |= MOD_FLAGS[mod]
        self._post(keycode, True)
        self._held.append(keycode)

    def _release(self, code: str, mod: Mod | None = None) -> None:
        keycode = self._keycode(code)
        if mod is not None:
            self._flags &= ~MOD_FLAGS[mod]
        self._post(keycode, False)
        if keycode in self._held:
            self._held.remove(keycode)

    @staticmethod
    def _keycode(code: str) -> int:
        try:
            return MAC_KEYCODES[code]
        except KeyError as exc:
            raise ValueError(f"no macOS key code known for {code!r}") from exc

    def tap(self, tap: KeyTap, hold_s: float) -> None:
        mods = [m for m in MOD_CODES if m in tap.mods]
        try:
            for m in mods:
                self._press(MOD_CODES[m], m)
            if mods:
                time.sleep(hold_s / 2)
            if tap.code is not None:
                self._press(tap.code)
                time.sleep(hold_s)
                self._release(tap.code)
            else:
                self._tap_keysym(tap.keysym or 0, hold_s)
        finally:
            for m in reversed(mods):
                self._release(MOD_CODES[m], m)
            if mods:
                time.sleep(hold_s / 2)

    def _tap_keysym(self, keysym: int, hold_s: float) -> None:
        if keysym in CONTROL_KEYSYM_CODES:
            code = CONTROL_KEYSYM_CODES[keysym]
            self._press(code)
            time.sleep(hold_s)
            self._release(code)
            return
        char = char_for_keysym(keysym)
        if char is None:
            raise ValueError(f"cannot type keysym {keysym:#x} on macOS")
        for down in (True, False):
            ev = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
            Quartz.CGEventKeyboardSetUnicodeString(ev, len(char), char)
            Quartz.CGEventSetFlags(ev, self._flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            if down:
                time.sleep(hold_s)

    def release_all(self) -> None:
        self._flags = 0
        for keycode in reversed(list(self._held)):
            self._post(keycode, False, flags=0)
        self._held.clear()

    def close(self) -> None:
        self.release_all()
