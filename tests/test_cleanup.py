from dcdclip.ocr.cleanup import normalise_console_text


def test_typographic_characters_become_ascii():
    text = "run ‘sudo cloud-init schema —system’ “now” – ok  \n\n"
    assert normalise_console_text(text) == "run 'sudo cloud-init schema --system' \"now\" - ok"


def test_long_option_dash_runs_collapse_but_separators_stay():
    assert normalise_console_text("systemctl enable ---now x ----system") == (
        "systemctl enable --now x --system"
    )
    assert normalise_console_text("--- ping statistics ---") == "--- ping statistics ---"
    assert normalise_console_text("-------- sep") == "-------- sep"


def test_trailing_whitespace_stripped_but_indent_kept():
    assert normalise_console_text("  a  \n b \n") == "  a\n b"
