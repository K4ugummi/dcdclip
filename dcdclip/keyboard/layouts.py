"""Guest keyboard layout data.

Each entry: code name -> (plain, Shift, AltGr, AltGr+Shift). Only the characters relevant
for typing text are modelled; navigation keys are handled by the planner directly.
"""

from __future__ import annotations

import string

from dcdclip.keyboard.model import Layout, Mod


def _letters(swap: dict[str, str] | None = None, altgr: dict[str, str] | None = None):
    """KeyA..KeyZ with the US letter placement; ``swap`` moves letters (e.g. y/z)."""
    swap = swap or {}
    altgr = altgr or {}
    keys: dict[str, tuple[str | None, ...]] = {}
    for letter in string.ascii_lowercase:
        code = f"Key{letter.upper()}"
        actual = swap.get(letter, letter)
        keys[code] = (actual, actual.upper(), altgr.get(actual), None)
    return keys


_COMMON: dict[str, tuple[str | None, ...]] = {"Space": (" ",)}

US = Layout(
    "us",
    "English (US)",
    {
        **_COMMON,
        **_letters(),
        "Backquote": ("`", "~"),
        "Digit1": ("1", "!"),
        "Digit2": ("2", "@"),
        "Digit3": ("3", "#"),
        "Digit4": ("4", "$"),
        "Digit5": ("5", "%"),
        "Digit6": ("6", "^"),
        "Digit7": ("7", "&"),
        "Digit8": ("8", "*"),
        "Digit9": ("9", "("),
        "Digit0": ("0", ")"),
        "Minus": ("-", "_"),
        "Equal": ("=", "+"),
        "BracketLeft": ("[", "{"),
        "BracketRight": ("]", "}"),
        "Backslash": ("\\", "|"),
        "Semicolon": (";", ":"),
        "Quote": ("'", '"'),
        "Comma": (",", "<"),
        "Period": (".", ">"),
        "Slash": ("/", "?"),
    },
)

_DE_KEYS: dict[str, tuple[str | None, ...]] = {
    **_COMMON,
    **_letters(swap={"y": "z", "z": "y"}, altgr={"q": "@", "e": "€", "m": "µ"}),
    "Backquote": (None, "°"),
    "Digit1": ("1", "!"),
    "Digit2": ("2", '"', "²"),
    "Digit3": ("3", "§", "³"),
    "Digit4": ("4", "$"),
    "Digit5": ("5", "%"),
    "Digit6": ("6", "&"),
    "Digit7": ("7", "/", "{"),
    "Digit8": ("8", "(", "["),
    "Digit9": ("9", ")", "]"),
    "Digit0": ("0", "=", "}"),
    "Minus": ("ß", "?", "\\"),
    "Equal": (None, None),
    "BracketLeft": ("ü", "Ü"),
    "BracketRight": ("+", "*", "~"),
    "Backslash": ("#", "'"),
    "Semicolon": ("ö", "Ö"),
    "Quote": ("ä", "Ä"),
    "Comma": (",", ";"),
    "Period": (".", ":"),
    "Slash": ("-", "_"),
    "IntlBackslash": ("<", ">", "|"),
}

DE = Layout(
    "de",
    "German (with dead keys ^ ´ `, Windows and Linux default)",
    _DE_KEYS,
    dead_keys={
        ("Backquote", Mod.NONE): "^",
        ("Equal", Mod.NONE): "´",
        ("Equal", Mod.SHIFT): "`",
    },
)

DE_NODEADKEYS = Layout(
    "de-nodeadkeys",
    "German (Linux 'nodeadkeys' variant)",
    {
        **_DE_KEYS,
        "Backquote": ("^", "°"),
        "Equal": ("´", "`"),
    },
)

LAYOUTS: dict[str, Layout] = {layout.name: layout for layout in (US, DE, DE_NODEADKEYS)}

DEFAULT_GUEST_LAYOUT = "us"
DEFAULT_SERVER_LAYOUT = "us"


def get_layout(name: str) -> Layout:
    try:
        return LAYOUTS[name]
    except KeyError as exc:
        raise ValueError(f"unknown keyboard layout {name!r}; known: {sorted(LAYOUTS)}") from exc
