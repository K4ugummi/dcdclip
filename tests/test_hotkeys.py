import pytest

pytest.importorskip("Xlib")

from Xlib import X  # noqa: E402

from dcdclip.windows.hotkeys_x11 import parse_hotkey  # noqa: E402


def test_parse_hotkey():
    assert parse_hotkey("ctrl+alt+v") == (X.ControlMask | X.Mod1Mask, "v")
    assert parse_hotkey("Ctrl + Alt + Escape") == (X.ControlMask | X.Mod1Mask, "escape")
    with pytest.raises(ValueError):
        parse_hotkey("hyper+v")
