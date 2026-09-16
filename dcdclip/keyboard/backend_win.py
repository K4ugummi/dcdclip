"""Windows keyboard backend using ``SendInput`` (ctypes, no extra dependency).

Physical keys are sent as scan codes (``KEYEVENTF_SCANCODE``) so the browser sees the right
``KeyboardEvent.code``; keysyms are sent as Unicode characters (``KEYEVENTF_UNICODE``), which
browsers report as the key value with an empty code.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from dcdclip.keyboard.keycodes_win import VK, scancode_for_code
from dcdclip.keyboard.model import CONTROL_KEYSYM_CODES, Mod, char_for_keysym
from dcdclip.keyboard.planner import KeyTap

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


MOD_CODES: dict[Mod, str] = {
    Mod.SHIFT: "ShiftLeft",
    Mod.ALTGR: "AltRight",  # Windows treats right Alt as AltGr on layouts that have it
    Mod.CTRL: "ControlLeft",
    Mod.ALT: "AltLeft",
}


class WinKeyboard:
    name = "windows-sendinput"

    def __init__(self) -> None:
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._user32.SendInput.restype = wintypes.UINT
        self._held: list[tuple[str, int, bool]] = []  # (kind, value, extended)

    # -- low level -----------------------------------------------------------------------
    def _send(self, inputs: list[INPUT]) -> None:
        arr = (INPUT * len(inputs))(*inputs)
        sent = self._user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            raise RuntimeError(f"SendInput failed: error {ctypes.get_last_error()}")

    @staticmethod
    def _scan_input(scan: int, extended: bool, up: bool) -> INPUT:
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if extended else 0)
        flags |= KEYEVENTF_KEYUP if up else 0
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, scan, flags, 0, 0))

    @staticmethod
    def _unicode_input(unit: int, up: bool) -> INPUT:
        flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, unit, flags, 0, 0))

    @staticmethod
    def _vk_input(vk: int, up: bool) -> INPUT:
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0))

    def _press_code(self, code: str) -> None:
        scan, ext = scancode_for_code(code)
        self._send([self._scan_input(scan, ext, up=False)])
        self._held.append(("scan", scan, ext))

    def _release_code(self, code: str) -> None:
        scan, ext = scancode_for_code(code)
        self._send([self._scan_input(scan, ext, up=True)])
        self._held = [h for h in self._held if h != ("scan", scan, ext)]

    # -- backend API ---------------------------------------------------------------------
    def tap(self, tap: KeyTap, hold_s: float) -> None:
        mod_codes = [MOD_CODES[m] for m in MOD_CODES if m in tap.mods]
        try:
            for code in mod_codes:
                self._press_code(code)
            if mod_codes:
                time.sleep(hold_s / 2)
            if tap.code is not None:
                self._press_code(tap.code)
                time.sleep(hold_s)
                self._release_code(tap.code)
            else:
                self._tap_keysym(tap.keysym or 0, hold_s)
        finally:
            for code in reversed(mod_codes):
                self._release_code(code)
            if mod_codes:
                time.sleep(hold_s / 2)

    def _tap_keysym(self, keysym: int, hold_s: float) -> None:
        if keysym in CONTROL_KEYSYM_CODES:
            code = CONTROL_KEYSYM_CODES[keysym]
            self._press_code(code)
            time.sleep(hold_s)
            self._release_code(code)
            return
        char = char_for_keysym(keysym)
        if char is None:
            raise ValueError(f"cannot type keysym {keysym:#x} on Windows")
        # UTF-16 code units (surrogate pairs for astral characters)
        units = list(memoryview(char.encode("utf-16-le")).cast("H"))
        self._send([self._unicode_input(u, up=False) for u in units])
        time.sleep(hold_s)
        self._send([self._unicode_input(u, up=True) for u in units])

    def release_all(self) -> None:
        for kind, value, ext in reversed(list(self._held)):
            if kind == "scan":
                self._send([self._scan_input(value, ext, up=True)])
        self._held.clear()

    def close(self) -> None:
        self.release_all()


__all__ = ["WinKeyboard", "VK"]
