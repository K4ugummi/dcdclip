from dcdclip.ocr.engine import _Word, reconstruct_lines


def w(text, left, top, cw=10, h=14, key=(1, 1, 1)):
    return _Word(text, left, top, cw * len(text), h, key)


def test_columns_and_blank_lines_reconstructed():
    words = [
        w("NAME", 0, 0),
        w("TYPE", 200, 0),
        w("lan", 0, 20, key=(1, 1, 2)),
        w("ethernet", 200, 20, key=(1, 1, 2)),
        # two blank lines, then an indented line
        w("done", 40, 80, key=(1, 2, 1)),
    ]
    assert reconstruct_lines(words) == (
        "NAME                TYPE\nlan                 ethernet\n\n\n    done"
    )


def test_empty():
    assert reconstruct_lines([]) == ""
