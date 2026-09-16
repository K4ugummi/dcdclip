"""Windows scan codes (PC/AT set 1) for W3C ``KeyboardEvent.code`` names. Pure data."""

from __future__ import annotations

from dcdclip.keyboard.backend_x11 import X11_KEYCODES

# Keys that use the 0xE0 prefix (KEYEVENTF_EXTENDEDKEY) and whose scan code differs
# from the evdev value.
EXTENDED: dict[str, int] = {
    "NumpadEnter": 0x1C,
    "ControlRight": 0x1D,
    "NumpadDivide": 0x35,
    "AltRight": 0x38,
    "Home": 0x47,
    "ArrowUp": 0x48,
    "PageUp": 0x49,
    "ArrowLeft": 0x4B,
    "ArrowRight": 0x4D,
    "End": 0x4F,
    "ArrowDown": 0x50,
    "PageDown": 0x51,
    "Insert": 0x52,
    "Delete": 0x53,
    "MetaLeft": 0x5B,
}


def scancode_for_code(code: str) -> tuple[int, bool]:
    """Return (scan code, extended?) for a physical key name.

    For the main keyboard block the Linux evdev key codes (X11 keycode - 8) coincide with
    the AT set 1 scan codes, so the X11 table is reused for everything not in ``EXTENDED``.
    """
    if code in EXTENDED:
        return EXTENDED[code], True
    try:
        return X11_KEYCODES[code] - 8, False
    except KeyError as exc:
        raise ValueError(f"no Windows scan code known for {code!r}") from exc


# Virtual-key codes needed for non-character keys and hotkeys.
VK: dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}
