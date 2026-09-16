"""Window backend interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def as_mss(self) -> dict[str, int]:
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class WindowInfo:
    id: int
    title: str
    app_class: str  # e.g. "firefox", "google-chrome"
    pid: int | None = None

    def label(self) -> str:
        return f"[{self.app_class}] {self.title}"


class WindowBackend(Protocol):
    name: str

    def list_windows(self) -> list[WindowInfo]: ...

    def active_window_id(self) -> int | None: ...

    def activate(self, window_id: int) -> None: ...

    def geometry(self, window_id: int) -> Rect | None:
        """Client area of the window in screen coordinates (or ``None`` if gone)."""

    def close(self) -> None: ...


def matches_filter(win: WindowInfo, title_filter: str, classes: tuple[str, ...]) -> bool:
    """Default filter for candidate console windows."""
    if title_filter and title_filter.lower() not in win.title.lower():
        return False
    return not classes or any(c in win.app_class.lower() for c in classes)
