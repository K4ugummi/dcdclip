"""Persistent settings. Never stores the text being typed or OCR results."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "dcdclip"


@dataclass
class Settings:
    # target window
    window_title_filter: str = "Remote Console"
    window_classes: list[str] = field(default_factory=lambda: ["firefox", "chrome", "chromium"])
    # keyboard
    guest_layout: str = "us"
    server_layout: str = "us"
    transport: str = "scancode"
    delay_ms: int = 30
    newline: str = "enter"
    tab: str = "tab"
    tab_spaces: int = 4
    indent: str = "keep"
    countdown_s: int = 3
    activate_delay_ms: int = 500
    clear_after_typing: bool = True
    hotkey_type: str = "ctrl+alt+v"
    hotkey_abort: str = "ctrl+alt+escape"
    hotkeys_enabled: bool = True
    # ocr
    ocr_lang: str = "eng"
    ocr_psm: int = 6
    ocr_scale: int = 2
    ocr_threshold: bool = False
    ocr_cleanup: bool = True
    ocr_auto_copy: bool = False

    @classmethod
    def path(cls) -> Path:
        return config_dir() / "config.json"

    @classmethod
    def load(cls) -> Settings:
        try:
            raw = json.loads(cls.path().read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        p = self.path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2), "utf-8")
