"""OCR engines behind one interface. Tesseract first; others can be added."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from statistics import median
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class OcrOptions:
    lang: str = "eng"  # tesseract language string, e.g. "deu+eng"
    psm: int = 6  # 6 = assume a single uniform block of text
    reconstruct_layout: bool = True  # rebuild lines/columns from word positions (monospace)


class OcrEngine(Protocol):
    name: str

    def available(self) -> tuple[bool, str]:
        """(usable?, human readable reason/version)."""

    def recognize(self, img: Image.Image, opts: OcrOptions) -> str: ...


@dataclass
class _Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    line_key: tuple[int, int, int]

    @property
    def right(self) -> int:
        return self.left + self.width


def reconstruct_lines(words: list[_Word]) -> str:
    """Rebuild console text from word boxes.

    Console output is monospace, so horizontal gaps translate to a number of spaces and
    vertical gaps to blank lines. Tesseract's own text output separates lines it considers
    paragraphs with empty lines and drops column alignment, which is useless for tables.
    """
    if not words:
        return ""
    global_char_w = max(median(w.width / max(len(w.text), 1) for w in words), 1.0)

    lines: dict[tuple[int, int, int], list[_Word]] = {}
    for w in words:
        lines.setdefault(w.line_key, []).append(w)
    ordered = sorted(lines.values(), key=lambda ws: min(x.top for x in ws))
    tops = [median(x.top for x in ws) for ws in ordered]
    heights = [median(x.height for x in ws) for ws in ordered]
    # One line of spacing = the smallest plausible gap between consecutive lines. Deltas
    # smaller than most of a glyph height are split lines, not real lines.
    min_delta = median(heights) * 0.7
    deltas = [b - a for a, b in zip(tops, tops[1:], strict=False) if b - a >= min_delta]
    line_h = min(deltas) if deltas else median(heights) * 1.3
    left_margin = min(w.left for w in words)

    out: list[str] = []
    prev_top: float | None = None
    for ws, top in zip(ordered, tops, strict=False):
        if prev_top is not None and line_h > 0:
            blank = round((top - prev_top) / line_h) - 1
            out.extend([""] * max(blank, 0))
        prev_top = top
        ws = sorted(ws, key=lambda x: x.left)
        # Per-line width estimate copes with mixed fonts (browser chrome vs console).
        char_w = max(median(x.width / max(len(x.text), 1) for x in ws), 1.0)
        if len(ws) < 3:
            char_w = global_char_w
        text = " " * max(round((ws[0].left - left_margin) / char_w), 0)
        cursor = ws[0].left
        for w in ws:
            gap = w.left - cursor
            if text and not text.isspace():
                text += " " * max(round(gap / char_w), 1)
            elif gap > 0 and text:
                text += " " * max(round(gap / char_w), 0)
            text += w.text
            cursor = w.right
        out.append(text.rstrip())
    return "\n".join(out)


class TesseractEngine:
    name = "tesseract"

    def available(self) -> tuple[bool, str]:
        if shutil.which("tesseract") is None:
            return False, (
                "tesseract binary not found. Linux: sudo apt install tesseract-ocr "
                "tesseract-ocr-eng tesseract-ocr-deu; macOS: brew install tesseract; "
                "Windows: UB-Mannheim installer, then add it to PATH."
            )
        try:
            import pytesseract

            version = pytesseract.get_tesseract_version()
        except Exception as exc:  # noqa: BLE001 - report anything to the user
            return False, f"pytesseract error: {exc}"
        return True, f"tesseract {version}"

    def recognize(self, img: Image.Image, opts: OcrOptions) -> str:
        import pytesseract

        config = f"--psm {opts.psm} -c preserve_interword_spaces=1"
        if not opts.reconstruct_layout:
            return pytesseract.image_to_string(img, lang=opts.lang, config=config).rstrip("\n")
        data = pytesseract.image_to_data(
            img, lang=opts.lang, config=config, output_type=pytesseract.Output.DICT
        )
        words: list[_Word] = []
        for i, text in enumerate(data["text"]):
            if not str(text).strip() or int(data["conf"][i]) < 0:
                continue
            words.append(
                _Word(
                    text=str(text),
                    left=int(data["left"][i]),
                    top=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                    line_key=(
                        int(data["block_num"][i]),
                        int(data["par_num"][i]),
                        int(data["line_num"][i]),
                    ),
                )
            )
        return reconstruct_lines(words)


def default_engine() -> OcrEngine:
    return TesseractEngine()
