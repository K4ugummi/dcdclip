"""Screenshots of screen regions (mss, works on X11, Windows and macOS)."""

from __future__ import annotations

import mss
from PIL import Image

from dcdclip.windows.base import Rect


def clamp_to_screen(rect: Rect, screen: Rect) -> Rect:
    """Intersect ``rect`` with the visible screen; windows may hang off the edge."""
    x1 = max(rect.x, screen.x)
    y1 = max(rect.y, screen.y)
    x2 = min(rect.x + rect.width, screen.x + screen.width)
    y2 = min(rect.y + rect.height, screen.y + screen.height)
    return Rect(x1, y1, max(x2 - x1, 0), max(y2 - y1, 0))


def capture_rect(rect: Rect) -> Image.Image:
    with mss.mss() as sct:
        virtual = sct.monitors[0]  # union of all monitors
        screen = Rect(virtual["left"], virtual["top"], virtual["width"], virtual["height"])
        clipped = clamp_to_screen(rect, screen)
        if clipped.width <= 0 or clipped.height <= 0:
            raise ValueError(f"capture rectangle {rect} lies outside the screen {screen}")
        shot = sct.grab(clipped.as_mss())
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
