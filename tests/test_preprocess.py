from PIL import Image, ImageDraw

from dcdclip.ocr.preprocess import PreprocessOptions, is_dark, preprocess


def _console_like(dark: bool) -> Image.Image:
    bg, fg = ((20, 20, 20), (220, 220, 220)) if dark else ((255, 255, 255), (0, 0, 0))
    img = Image.new("RGB", (120, 40), bg)
    ImageDraw.Draw(img).text((5, 10), "root@vm:~#", fill=fg)
    return img


def test_is_dark():
    assert is_dark(_console_like(True))
    assert not is_dark(_console_like(False))


def test_preprocess_scales_and_binarises_with_dark_text_on_white():
    out = preprocess(_console_like(True), PreprocessOptions(scale=2, threshold=True))
    assert out.size == (240, 80)
    assert out.mode == "L"
    colors = {c for _, c in out.getcolors()}
    assert colors <= {0, 255}
    # background must be white after inversion
    assert out.getpixel((0, 0)) == 255
