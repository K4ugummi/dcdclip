"""Image preprocessing tuned for console/terminal text."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True)
class PreprocessOptions:
    scale: int = 2  # upscale factor, console fonts are small
    threshold: bool = False  # binarise (Tesseract's own binarisation did better on console fonts)
    auto_invert: bool = True  # dark terminals -> black text on white


def is_dark(img: Image.Image) -> bool:
    gray = img.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    dark = sum(hist[:128])
    return dark > total / 2


def _otsu_threshold(gray: Image.Image) -> int:
    hist = gray.histogram()
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))
    sum_bg = 0.0
    weight_bg = 0
    best_t, best_var = 128, -1.0
    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def preprocess(img: Image.Image, opts: PreprocessOptions | None = None) -> Image.Image:
    opts = opts or PreprocessOptions()
    gray = img.convert("L")
    if opts.auto_invert and is_dark(gray):
        gray = ImageOps.invert(gray)
    if opts.scale > 1:
        gray = gray.resize((gray.width * opts.scale, gray.height * opts.scale), Image.LANCZOS)
    if opts.threshold:
        t = _otsu_threshold(gray)
        gray = gray.point(lambda p, t=t: 255 if p > t else 0)
    return gray
