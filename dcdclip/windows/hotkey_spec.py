"""Platform independent parsing of hotkey specs such as ``"ctrl+alt+v"``."""

from __future__ import annotations

from dataclasses import dataclass

_MOD_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "super": "super",
    "win": "super",
    "cmd": "super",
    "command": "super",
    "meta": "super",
}


@dataclass(frozen=True)
class HotkeySpec:
    mods: frozenset[str]  # subset of {"ctrl", "shift", "alt", "super"}
    key: str  # lower-case key name: "v", "escape", "f5", ...


def parse_hotkey_spec(spec: str) -> HotkeySpec:
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    mods = set()
    for part in parts[:-1]:
        try:
            mods.add(_MOD_ALIASES[part])
        except KeyError as exc:
            raise ValueError(f"unknown modifier {part!r} in hotkey {spec!r}") from exc
    return HotkeySpec(frozenset(mods), parts[-1])
