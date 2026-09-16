"""Keyboard model.

Physical keys are identified by their W3C ``KeyboardEvent.code`` name ("KeyA", "Digit1",
"BracketLeft", ...). This is layout independent and is the vocabulary shared by browsers,
noVNC and our backends. A *layout* maps characters to (physical key, modifiers).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto


class Mod(Flag):
    NONE = 0
    SHIFT = auto()
    ALTGR = auto()
    CTRL = auto()
    ALT = auto()


LEVELS: tuple[Mod, ...] = (Mod.NONE, Mod.SHIFT, Mod.ALTGR, Mod.ALTGR | Mod.SHIFT)


@dataclass(frozen=True)
class KeyStroke:
    """A physical key plus modifiers. ``dead`` marks a dead key (needs a following Space)."""

    code: str
    mods: Mod = Mod.NONE
    dead: bool = False


class Layout:
    """Character <-> key stroke mapping for one keyboard layout.

    ``keys`` maps a code name to up to four characters for the levels plain, Shift, AltGr,
    AltGr+Shift (``None`` or missing = nothing on that level). ``dead_keys`` maps
    ``(code, mods)`` to the character the dead key produces when followed by Space.
    """

    def __init__(
        self,
        name: str,
        description: str,
        keys: dict[str, tuple[str | None, ...]],
        dead_keys: dict[tuple[str, Mod], str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self._by_char: dict[str, KeyStroke] = {}
        self._by_stroke: dict[tuple[str, Mod], str] = {}
        for code, chars in keys.items():
            for mods, ch in zip(LEVELS, chars, strict=False):
                if ch is None:
                    continue
                self._by_stroke[(code, mods)] = ch
                self._by_char.setdefault(ch, KeyStroke(code, mods))
        for (code, mods), ch in (dead_keys or {}).items():
            self._by_char.setdefault(ch, KeyStroke(code, mods, dead=True))

    def stroke_for(self, char: str) -> KeyStroke | None:
        return self._by_char.get(char)

    def char_for(self, code: str, mods: Mod) -> str | None:
        """Character produced by a (non-dead) key at the given level, or ``None``."""
        return self._by_stroke.get((code, mods & (Mod.SHIFT | Mod.ALTGR)))

    def supports(self, char: str) -> bool:
        return char in self._by_char

    def unsupported_chars(self, text: str) -> set[str]:
        return {c for c in text if c not in ("\n", "\r", "\t") and not self.supports(c)}

    def __repr__(self) -> str:
        return f"Layout({self.name!r})"


def keysym_for_char(char: str) -> int:
    """X11 keysym for a character (Latin-1 keysyms coincide with code points)."""
    cp = ord(char)
    if 0x20 <= cp <= 0x7E or 0xA0 <= cp <= 0xFF:
        return cp
    return 0x01000000 | cp


# Well known non-character keysyms.
XK_RETURN = 0xFF0D
XK_TAB = 0xFF09
XK_SPACE = 0x20
XK_BACKSPACE = 0xFF08
XK_ESCAPE = 0xFF1B
