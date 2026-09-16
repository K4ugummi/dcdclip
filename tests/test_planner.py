import pytest

from dcdclip.keyboard.layouts import DE, US
from dcdclip.keyboard.model import XK_RETURN, XK_SPACE, XK_TAB, Mod
from dcdclip.keyboard.planner import (
    IndentMode,
    KeyTap,
    NewlineMode,
    TabMode,
    Transport,
    TypeOptions,
    Unsupported,
    normalise_text,
    plan_text,
)


def keysyms(plan):
    return [(s.keysym, s.mods) for s in plan.steps if isinstance(s, KeyTap)]


def test_keysym_transport_de_guest_us_server():
    # guest 'z' sits on physical KeyY; en-us has 'y' there -> host must send keysym 'y'
    plan = plan_text("zZ", DE, US, TypeOptions(transport=Transport.KEYSYM))
    assert keysyms(plan) == [(ord("y"), Mod.NONE), (ord("Y"), Mod.NONE)]


def test_keysym_transport_altgr_holds_altgr_and_sends_plain_keysym():
    # guest '{' = AltGr+Digit7; en-us has '7' on Digit7 -> hold AltGr, send keysym '7'
    plan = plan_text("{@", DE, US, TypeOptions(transport=Transport.KEYSYM))
    assert plan.steps == [
        KeyTap(mods=Mod.ALTGR, keysym=ord("7"), label="{", force_remap=True),
        KeyTap(mods=Mod.ALTGR, keysym=ord("q"), label="@", force_remap=True),
    ]


def test_keysym_transport_key_missing_on_server_layout_unsupported():
    # guest '<' sits on IntlBackslash, which the en-us server keymap does not know
    plan = plan_text("<", DE, US, TypeOptions(transport=Transport.KEYSYM))
    assert plan.steps == [Unsupported("<")]
    assert plan.unsupported == ["<"]


def test_keysym_transport_dead_key_adds_space():
    plan = plan_text("^", DE, US, TypeOptions(transport=Transport.KEYSYM))
    assert keysyms(plan) == [(ord("`"), Mod.NONE), (XK_SPACE, Mod.NONE)]


def test_scancode_transport():
    plan = plan_text("z@", DE, US, TypeOptions(transport=Transport.SCANCODE))
    assert plan.steps == [
        KeyTap(code="KeyY", label="z"),
        KeyTap(code="KeyQ", mods=Mod.ALTGR, label="@"),
    ]


def test_newline_and_tab_modes():
    plan = plan_text(
        "a\n\tb", DE, US, TypeOptions(transport=Transport.KEYSYM, newline=NewlineMode.SHIFT_ENTER)
    )
    assert keysyms(plan) == [
        (ord("a"), Mod.NONE),
        (XK_RETURN, Mod.SHIFT),
        (XK_TAB, Mod.NONE),
        (ord("b"), Mod.NONE),
    ]
    plan = plan_text("\tb", DE, US, TypeOptions(tab=TabMode.SPACES, tab_spaces=2))
    assert [s.label for s in plan.steps] == [" ", " ", "b"]


def test_unknown_char_reported_once():
    plan = plan_text("ññ", DE, US, TypeOptions())
    assert plan.unsupported == ["ñ"]
    assert plan.taps == 0


def test_normalise_indent():
    text = "    a\n      b\n"
    assert normalise_text(text, TypeOptions(indent=IndentMode.COMMON)) == "a\n  b\n"
    assert normalise_text(text, TypeOptions(indent=IndentMode.STRIP)) == "a\nb\n"
    assert normalise_text("a\r\nb", TypeOptions()) == "a\nb"
    assert normalise_text("a", TypeOptions(trailing_newline=True)) == "a\n"


def test_keytap_validation():
    with pytest.raises(ValueError):
        KeyTap()
    with pytest.raises(ValueError):
        KeyTap(code="KeyA", keysym=1)


def test_default_transport_is_scancode_and_us_guest_types_ls_al():
    from dcdclip.keyboard.layouts import DEFAULT_GUEST_LAYOUT, get_layout

    plan = plan_text("ls -al", get_layout(DEFAULT_GUEST_LAYOUT), US, TypeOptions())
    assert [(s.code, s.mods) for s in plan.steps] == [
        ("KeyL", Mod.NONE),
        ("KeyS", Mod.NONE),
        ("Space", Mod.NONE),
        ("Minus", Mod.NONE),
        ("KeyA", Mod.NONE),
        ("KeyL", Mod.NONE),
    ]
