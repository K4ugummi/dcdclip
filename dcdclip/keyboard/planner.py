"""Turn text into a sequence of key taps for a given guest layout and transport.

The chain a key press travels through::

    host backend -> host X server (host layout) -> browser -> VNC JS client
        -> VNC server (server keymap, usually en-us) -> guest OS (guest layout)

Two transports are modelled:

* ``SCANCODE``: the browser client forwards the *physical* key (``KeyboardEvent.code``,
  noVNC with QEMU extended key events). We press the physical key the guest layout needs.
* ``KEYSYM``: the browser client forwards the *keysym* the host produced; the VNC server
  translates it back to a scancode with its own (en-us) keymap. We therefore compute which
  en-us keysym sits on the physical key the guest layout needs and let the backend produce
  that keysym on the host by whatever means (host layout lookup or temporary remap).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from enum import StrEnum

from dcdclip.keyboard.model import (
    XK_RETURN,
    XK_SPACE,
    XK_TAB,
    KeyStroke,
    Layout,
    Mod,
    keysym_for_char,
)


class Transport(StrEnum):
    KEYSYM = "keysym"
    SCANCODE = "scancode"


class NewlineMode(StrEnum):
    ENTER = "enter"
    SHIFT_ENTER = "shift_enter"
    CTRL_ENTER = "ctrl_enter"


class TabMode(StrEnum):
    TAB = "tab"
    SPACES = "spaces"


class IndentMode(StrEnum):
    KEEP = "keep"
    COMMON = "common"  # textwrap.dedent
    STRIP = "strip"  # remove all leading whitespace per line


@dataclass(frozen=True)
class TypeOptions:
    transport: Transport = Transport.SCANCODE
    newline: NewlineMode = NewlineMode.ENTER
    tab: TabMode = TabMode.TAB
    tab_spaces: int = 4
    indent: IndentMode = IndentMode.KEEP
    trailing_newline: bool = False  # press Enter after the last line even if text lacks one


@dataclass(frozen=True)
class KeyTap:
    """One key press+release on the host.

    Exactly one of ``code`` (physical key) or ``keysym`` is set. ``mods`` are pressed
    around the key. ``label`` is only for previews/logging.
    """

    mods: Mod = Mod.NONE
    code: str | None = None
    keysym: int | None = None
    label: str = ""
    force_remap: bool = False  # keysym transport: never use the host layout's own key

    def __post_init__(self) -> None:
        if (self.code is None) == (self.keysym is None):
            raise ValueError("KeyTap needs exactly one of code or keysym")


@dataclass(frozen=True)
class Unsupported:
    char: str


Step = KeyTap | Unsupported


@dataclass
class TypePlan:
    steps: list[Step] = field(default_factory=list)

    @property
    def unsupported(self) -> list[str]:
        seen: list[str] = []
        for s in self.steps:
            if isinstance(s, Unsupported) and s.char not in seen:
                seen.append(s.char)
        return seen

    @property
    def taps(self) -> int:
        return sum(1 for s in self.steps if isinstance(s, KeyTap))


def normalise_text(text: str, opts: TypeOptions) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if opts.indent is IndentMode.COMMON:
        text = textwrap.dedent(text)
    elif opts.indent is IndentMode.STRIP:
        text = "\n".join(line.lstrip(" \t") for line in text.split("\n"))
    if opts.tab is TabMode.SPACES:
        text = text.replace("\t", " " * opts.tab_spaces)
    if opts.trailing_newline and not text.endswith("\n"):
        text += "\n"
    return text


def _control_tap(code: str, keysym: int, mods: Mod, transport: Transport, label: str) -> KeyTap:
    if transport is Transport.SCANCODE:
        return KeyTap(mods=mods, code=code, label=label)
    return KeyTap(mods=mods, keysym=keysym, label=label)


def _char_taps(
    char: str, stroke: KeyStroke, guest: Layout, server: Layout, transport: Transport
) -> list[Step]:
    if transport is Transport.SCANCODE:
        taps: list[Step] = [KeyTap(mods=stroke.mods, code=stroke.code, label=char)]
        if stroke.dead:
            taps.append(KeyTap(code="Space", label="Space"))
        return taps

    # KEYSYM: which keysym does the server keymap have on that physical key + level?
    # AltGr is not part of the keysym: we hold AltGr on the host (the client forwards the
    # AltGr key itself) and send the keysym of the *un-shifted-by-AltGr* level. The backend
    # must then use a remapped spare key, otherwise the host layout would apply AltGr too.
    altgr = bool(stroke.mods & Mod.ALTGR)
    server_char = server.char_for(stroke.code, stroke.mods & ~Mod.ALTGR)
    if server_char is None:
        return [Unsupported(char)]
    extra = stroke.mods & ~Mod.SHIFT  # ctrl/alt/altgr are pressed on the host
    taps = [KeyTap(mods=extra, keysym=keysym_for_char(server_char), label=char, force_remap=altgr)]
    if stroke.dead:
        taps.append(KeyTap(keysym=XK_SPACE, label="Space"))
    return taps


def plan_text(text: str, guest: Layout, server: Layout, opts: TypeOptions) -> TypePlan:
    """Build the tap sequence for ``text``.

    ``server`` is the layout of the VNC server keymap (only used for ``KEYSYM`` transport).
    """
    text = normalise_text(text, opts)
    plan = TypePlan()
    t = opts.transport
    newline_mods = {
        NewlineMode.ENTER: Mod.NONE,
        NewlineMode.SHIFT_ENTER: Mod.SHIFT,
        NewlineMode.CTRL_ENTER: Mod.CTRL,
    }[opts.newline]
    for char in text:
        if char == "\n":
            plan.steps.append(_control_tap("Enter", XK_RETURN, newline_mods, t, "Enter"))
        elif char == "\t":
            plan.steps.append(_control_tap("Tab", XK_TAB, Mod.NONE, t, "Tab"))
        else:
            stroke = guest.stroke_for(char)
            if stroke is None:
                plan.steps.append(Unsupported(char))
            else:
                plan.steps.extend(_char_taps(char, stroke, guest, server, t))
    return plan
