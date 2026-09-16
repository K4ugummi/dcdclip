"""The Windows and macOS key tables must cover every key the layouts and planner use."""

from dcdclip.keyboard.keycodes_mac import MAC_KEYCODES, code_for_hotkey_name
from dcdclip.keyboard.keycodes_win import EXTENDED, scancode_for_code
from dcdclip.keyboard.keycodes_x11 import X11_KEYCODES
from dcdclip.keyboard.layouts import LAYOUTS
from dcdclip.keyboard.model import Mod, char_for_keysym, keysym_for_char
from dcdclip.windows.hotkey_spec import parse_hotkey_spec

CONTROL_CODES = {
    "Enter",
    "Tab",
    "Space",
    "Backspace",
    "Escape",
    "ShiftLeft",
    "AltRight",
    "ControlLeft",
    "AltLeft",
}


def _layout_codes() -> set[str]:
    codes: set[str] = set()
    for layout in LAYOUTS.values():
        for (code, _mods), _ch in layout._by_stroke.items():
            codes.add(code)
        for stroke in layout._by_char.values():
            codes.add(stroke.code)
    return codes | CONTROL_CODES


def test_windows_scancodes_cover_layouts():
    for code in _layout_codes():
        scan, ext = scancode_for_code(code)
        assert 0 < scan < 0x80, code
    assert scancode_for_code("KeyA") == (0x1E, False)
    assert scancode_for_code("Enter") == (0x1C, False)
    assert scancode_for_code("IntlBackslash") == (0x56, False)
    assert scancode_for_code("AltRight") == (0x38, True)
    assert scancode_for_code("NumpadEnter") == (0x1C, True)
    assert set(EXTENDED) <= set(X11_KEYCODES)


def test_mac_keycodes_cover_layouts():
    for code in _layout_codes():
        assert code in MAC_KEYCODES, code
    assert MAC_KEYCODES["KeyA"] == 0 and MAC_KEYCODES["Enter"] == 36
    assert MAC_KEYCODES["AltRight"] == 61


def test_mac_keycodes_cover_x11_table_mostly():
    missing = set(X11_KEYCODES) - set(MAC_KEYCODES)
    assert missing <= {"ScrollLock", "Pause", "F13"} | {f"F{n}" for n in range(13, 25)}


def test_hotkey_spec_and_mac_names():
    spec = parse_hotkey_spec("Ctrl + Alt + V")
    assert spec.mods == {"ctrl", "alt"} and spec.key == "v"
    assert parse_hotkey_spec("cmd+shift+escape").mods == {"super", "shift"}
    assert code_for_hotkey_name("v") == "KeyV"
    assert code_for_hotkey_name("escape") == "Escape"
    assert code_for_hotkey_name("f5") == "F5"
    assert code_for_hotkey_name("7") == "Digit7"


def test_char_keysym_roundtrip():
    for ch in "a Z 7 - ä ß € {":
        assert char_for_keysym(keysym_for_char(ch)) == ch
    assert char_for_keysym(0xFF0D) is None  # Return


def test_mod_flags_distinct():
    assert Mod.SHIFT | Mod.ALTGR != Mod.SHIFT
