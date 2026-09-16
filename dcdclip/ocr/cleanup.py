"""Post-processing of OCR output for console text.

Tesseract likes to emit typographic quotes and dashes; in shell commands those are wrong.
"""

from __future__ import annotations

import re

_REPLACEMENTS: dict[str, str] = {
    "‘": "'",  # ‘
    "’": "'",  # ’
    "‚": "'",  # ‚
    "‛": "'",  # ‛
    "“": '"',  # “
    "”": '"',  # ”
    "„": '"',  # „
    "—": "--",  # — (Tesseract merges dash runs into em dashes; run length fixed below)
    "–": "-",  # –
    "−": "-",  # − (minus sign)
    " ": " ",  # nbsp
    "…": "...",  # …
    "´": "'",  # ´
    "•": "*",  # •
    "×": "x",  # ×
}


# A run of 1-4 dashes directly followed by a letter is a long option (`--system`); Tesseract
# frequently reads it as `-`, `---` or `----`. Runs of 5+ are separators and stay.
_LONG_OPTION = re.compile(r"(?<![-\w])-{3,4}(?=[A-Za-z])")


def normalise_console_text(text: str) -> str:
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = _LONG_OPTION.sub("--", text)
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip("\n")
