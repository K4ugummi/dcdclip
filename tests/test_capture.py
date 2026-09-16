from dcdclip.ocr.capture import clamp_to_screen
from dcdclip.windows.base import Rect


def test_clamp_partially_offscreen_window():
    screen = Rect(0, 0, 1920, 1080)
    assert clamp_to_screen(Rect(657, 82, 1376, 905), screen) == Rect(657, 82, 1263, 905)
    assert clamp_to_screen(Rect(-50, -20, 100, 100), screen) == Rect(0, 0, 50, 80)
    assert clamp_to_screen(Rect(3000, 0, 10, 10), screen).width == 0
