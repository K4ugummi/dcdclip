"""X11 keyboard backend using the XTEST extension (python-xlib).

Keycodes follow the evdev rule set used by every current X server on Linux
(``keycode = evdev code + 8``), so physical keys map to fixed keycodes regardless of the
configured host layout. Keysyms are looked up in the live host keymap; keysyms the host
layout cannot produce are typed by temporarily remapping a spare keycode (the same trick
``xdotool type`` uses), which is fine for the ``KEYSYM`` transport.
"""

from __future__ import annotations

import time

from Xlib import X, display
from Xlib.ext import xtest

from dcdclip.keyboard.keycodes_x11 import X11_KEYCODES
from dcdclip.keyboard.model import Mod
from dcdclip.keyboard.planner import KeyTap

MOD_KEYCODES: dict[Mod, int] = {
    Mod.SHIFT: X11_KEYCODES["ShiftLeft"],
    Mod.ALTGR: X11_KEYCODES["AltRight"],
    Mod.CTRL: X11_KEYCODES["ControlLeft"],
    Mod.ALT: X11_KEYCODES["AltLeft"],
}

# Index in the core keymap row -> modifiers needed on the host (XKB exposes a one-group,
# four-level layout as [L1, L2, L1, L2, L3, L4] through the core protocol).
_LEVEL_MODS: dict[int, Mod] = {
    0: Mod.NONE,
    1: Mod.SHIFT,
    2: Mod.NONE,
    3: Mod.SHIFT,
    4: Mod.ALTGR,
    5: Mod.ALTGR | Mod.SHIFT,
}


class X11Keyboard:
    name = "x11-xtest"

    def __init__(self, disp: display.Display | None = None) -> None:
        self.display = disp or display.Display()
        if not self.display.has_extension("XTEST"):
            raise RuntimeError("X server has no XTEST extension; cannot emulate key presses")
        self._min = self.display.display.info.min_keycode
        self._max = self.display.display.info.max_keycode
        self._held: list[int] = []
        self._spare: int | None = None
        self._spare_original: list[int] | None = None
        self.refresh_keymap()

    # -- keymap --------------------------------------------------------------------------
    def refresh_keymap(self) -> None:
        count = self._max - self._min + 1
        self._map: list[list[int]] = [
            list(row) for row in self.display.get_keyboard_mapping(self._min, count)
        ]

    def keycode_for_keysym(self, keysym: int) -> tuple[int, Mod] | None:
        best: tuple[int, int] | None = None  # (level index, keycode)
        for offset, row in enumerate(self._map):
            for idx, ks in enumerate(row):
                if ks == keysym and idx in _LEVEL_MODS and (best is None or idx < best[0]):
                    best = (idx, self._min + offset)
        if best is None:
            return None
        return best[1], _LEVEL_MODS[best[0]]

    def _find_spare_keycode(self) -> int:
        # Search from the top: high keycodes are unused on ordinary keyboards.
        for offset in range(len(self._map) - 1, -1, -1):
            if all(ks == 0 for ks in self._map[offset]):
                return self._min + offset
        raise RuntimeError("no spare keycode available for temporary remapping")

    def _remap_spare(self, keysym: int) -> int:
        if self._spare is None:
            self._spare = self._find_spare_keycode()
            self._spare_original = list(self._map[self._spare - self._min])
        width = len(self._map[0])
        self.display.change_keyboard_mapping(self._spare, [[keysym] * width])
        self.display.sync()
        time.sleep(0.03)  # let the browser process MappingNotify
        return self._spare

    def _restore_spare(self) -> None:
        if self._spare is not None and self._spare_original is not None:
            self.display.change_keyboard_mapping(self._spare, [self._spare_original])
            self.display.sync()

    # -- events --------------------------------------------------------------------------
    def _press(self, keycode: int) -> None:
        xtest.fake_input(self.display, X.KeyPress, keycode)
        self.display.sync()
        self._held.append(keycode)

    def _release(self, keycode: int) -> None:
        xtest.fake_input(self.display, X.KeyRelease, keycode)
        self.display.sync()
        if keycode in self._held:
            self._held.remove(keycode)

    def resolve(self, tap: KeyTap) -> tuple[int, Mod, bool]:
        """Return (keycode, host modifiers, used_temporary_remap) for a tap."""
        if tap.code is not None:
            try:
                return X11_KEYCODES[tap.code], tap.mods, False
            except KeyError as exc:
                raise ValueError(f"no X11 keycode known for {tap.code!r}") from exc
        assert tap.keysym is not None
        found = None if tap.force_remap else self.keycode_for_keysym(tap.keysym)
        if found is not None:
            return found[0], found[1] | tap.mods, False
        return self._remap_spare(tap.keysym), tap.mods, True

    def tap(self, tap: KeyTap, hold_s: float) -> None:
        keycode, mods, remapped = self.resolve(tap)
        mod_codes = [kc for mod, kc in MOD_KEYCODES.items() if mod in mods]
        try:
            for kc in mod_codes:
                self._press(kc)
            if mod_codes:
                time.sleep(hold_s / 2)
            self._press(keycode)
            time.sleep(hold_s)
            self._release(keycode)
            for kc in reversed(mod_codes):
                self._release(kc)
            if mod_codes:
                time.sleep(hold_s / 2)
        finally:
            if remapped:
                time.sleep(0.03)
                self._restore_spare()

    def release_all(self) -> None:
        for kc in list(self._held):
            self._release(kc)
        self._restore_spare()

    def close(self) -> None:
        self.release_all()
        self.display.close()
