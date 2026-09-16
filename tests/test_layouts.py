from dcdclip.keyboard.layouts import DE, DE_NODEADKEYS, US, get_layout
from dcdclip.keyboard.model import KeyStroke, Mod, keysym_for_char


def test_us_basic():
    assert US.stroke_for("a") == KeyStroke("KeyA")
    assert US.stroke_for("A") == KeyStroke("KeyA", Mod.SHIFT)
    assert US.stroke_for("@") == KeyStroke("Digit2", Mod.SHIFT)
    assert US.char_for("KeyY", Mod.NONE) == "y"
    assert US.char_for("KeyY", Mod.SHIFT) == "Y"
    assert US.char_for("KeyQ", Mod.ALTGR) is None


def test_de_letters_swapped_and_altgr():
    assert DE.stroke_for("z") == KeyStroke("KeyY")
    assert DE.stroke_for("y") == KeyStroke("KeyZ")
    assert DE.stroke_for("@") == KeyStroke("KeyQ", Mod.ALTGR)
    assert DE.stroke_for("{") == KeyStroke("Digit7", Mod.ALTGR)
    assert DE.stroke_for("|") == KeyStroke("IntlBackslash", Mod.ALTGR)
    assert DE.stroke_for("ß") == KeyStroke("Minus")
    assert DE.stroke_for("-") == KeyStroke("Slash")
    assert DE.stroke_for("_") == KeyStroke("Slash", Mod.SHIFT)
    assert DE.stroke_for("'") == KeyStroke("Backslash", Mod.SHIFT)


def test_de_dead_keys():
    assert DE.stroke_for("^") == KeyStroke("Backquote", Mod.NONE, dead=True)
    assert DE.stroke_for("`") == KeyStroke("Equal", Mod.SHIFT, dead=True)
    assert DE_NODEADKEYS.stroke_for("^") == KeyStroke("Backquote")


def test_unsupported_chars():
    assert DE.unsupported_chars("hello\n\tworld") == set()
    assert DE.unsupported_chars("ñ") == {"ñ"}
    assert US.unsupported_chars("ä") == {"ä"}


def test_keysym_for_char():
    assert keysym_for_char("a") == 0x61
    assert keysym_for_char("ä") == 0xE4
    assert keysym_for_char("€") == 0x01000000 | 0x20AC


def test_get_layout_unknown():
    import pytest

    with pytest.raises(ValueError):
        get_layout("nope")
