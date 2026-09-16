# dcdclip

**Clipboard workaround for the IONOS DCD Remote Console.**

The IONOS Data Center Designer (DCD) offers a browser based "Remote Console" for every VM.
It works like a VNC session in a browser tab, and it has no clipboard: you cannot paste text
into the VM and you cannot copy text out of it. `dcdclip` fills that gap from the outside:

- **Paste in**: paste text into `dcdclip`, it focuses the console window and *types* the
  text by emulating key presses on your machine, aware of the VM's keyboard layout.
- **Copy out**: `dcdclip` screenshots the console (a region you draw once) and runs OCR on
  it, so you can review, correct and copy the text.

It is a normal desktop application, no browser extension, no changes on the VM.

> Typical payloads are shell commands, passwords and SSH key contents. The text you type is
> never written to disk or logged, and it is cleared from the input box after typing.

## Status

| Platform | State |
| --- | --- |
| Linux (X11) | Working. |
| Windows | Experimental: implemented with `SendInput` and `RegisterHotKey`, needs testers. |
| macOS | Experimental: implemented with Quartz events; grant **Accessibility** (typing, hotkeys) and **Screen Recording** (window titles, OCR capture) permissions to `dcdclip.app`. Needs testers. |
| Linux (Wayland) | Not planned; needs uinput. Log in to an X11 session. |

Release candidates are published as portable archives under
[Releases](https://github.com/K4ugummi/dcdclip/releases).

## Install

### Portable archive

1. Download the archive for your platform from the releases page and unpack it.
2. Run `dcdclip` (Linux), `dcdclip.exe` (Windows) or `dcdclip.app` (macOS).
3. For OCR, install [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)
   so that the `tesseract` binary is on your `PATH`:
   - Debian/Ubuntu/Mint: `sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu`
   - Fedora/RHEL: `sudo dnf install tesseract tesseract-langpack-eng tesseract-langpack-deu`
   - macOS: `brew install tesseract`
   - Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)

The archives are unsigned. macOS will refuse to open the app until you run
`xattr -dr com.apple.quarantine dcdclip.app` once; Windows SmartScreen will warn.

### From source

Requires Python 3.12+.

```bash
git clone https://github.com/K4ugummi/dcdclip.git
cd dcdclip
python3 -m venv .venv && . .venv/bin/activate     # or: uv venv .venv
pip install -e ".[dev]"                             # or: uv pip install -e ".[dev]"
python -m dcdclip
```

## Usage

### Paste text into the VM

1. Open the DCD Remote Console in your browser and log into the VM as usual.
2. Start `dcdclip`. The target window list is pre-filtered to browser windows whose title
   contains "Remote Console"; pick yours (or untick the filter to see all windows).
3. In **Settings**, choose the **guest keyboard layout** of the VM (see below). Leave the
   transport on `scancode`.
4. Paste your text into the **Paste into console** tab. The line below the text box tells you
   how many key presses it takes and whether some characters cannot be typed with that
   layout.
5. Click **Type into console**. After the countdown the console is focused and typing
   starts. **Abort** stops immediately, as does the abort hotkey.

Hotkeys (configurable, on by default): `Ctrl+Alt+V` types the text right away without a
countdown, `Ctrl+Alt+Escape` aborts. Typing also stops by itself if the console window loses
focus, so nothing ends up in the wrong window.

Options worth knowing:

- **Newline as** Enter / Shift+Enter / Ctrl+Enter, e.g. for chat-like inputs.
- **Tab characters** as the Tab key or as spaces; **Indentation** can be stripped for editors
  with auto-indent (or use `:set paste` in vim).
- **Delay per key** (default 30 ms). Raise it if characters get lost over a slow link.
- **Press Enter at the end** to run a command directly.

### Which guest keyboard layout?

The DCD console forwards *physical* key positions to the VM. The VM then interprets them
with **its own** keyboard layout, so `dcdclip` needs to know that layout, not yours. Quick
check: type `z` and `-` by hand in the console. If the VM shows `y` and `ß` (or `&` for `-`
after Shift), it uses a different layout than your keyboard.

Available layouts: `us`, `de`, `de-nodeadkeys`. Adding a layout is a small data table in
`dcdclip/keyboard/layouts.py`; pull requests welcome.

### Copy text out of the VM

1. Open the **Copy from console (OCR)** tab.
2. Click **Select screen region…** and drag a rectangle around the VM screen inside the
   console (not the browser toolbar). **Capture last region again** repeats that rectangle.
3. The recognised text appears in the box, with columns and blank lines preserved. Check it,
   fix what Tesseract got wrong, and click **Copy to clipboard**.

OCR on a console font is good but not perfect: expect occasional confusion between `0`/`o`,
`l`/`1`, `[`/`C` and `]`/`1`. Long option dashes and quotes are normalised to ASCII
automatically. For German UIs set the OCR language to `deu+eng` in Settings.

## How it works

```
dcdclip ──XTEST key events──▶ X server ──▶ browser ──▶ DCD console (noVNC-style client)
                                                          │ physical key codes
                                                          ▼
                                                    VNC server ──▶ VM (guest layout)
```

- Physical keys are named by their W3C `KeyboardEvent.code` (`KeyY`, `Digit7`, ...). A guest
  layout maps each character to a physical key plus modifiers, dead keys get a trailing Space.
- Linux: key presses via the X11 XTEST extension, window focus via EWMH, hotkeys via `XGrabKey`.
  Windows: `SendInput` scan codes, `EnumWindows`/`SetForegroundWindow`, `RegisterHotKey`.
  macOS: `CGEventPost` key codes, `CGWindowList` plus Accessibility raise, a `CGEventTap`
  for hotkeys.
- OCR: screenshot with `mss`, grayscale and 2x upscale, Tesseract with word boxes, then the
  text is rebuilt from the box positions so monospace columns stay aligned.

The complete design, decisions and findings are in [`CLAUDE.md`](CLAUDE.md); the console
calibration procedure is in [`docs/console-calibration.md`](docs/console-calibration.md).

## Limitations

- Characters that do not exist on the selected guest layout are skipped (you are warned
  first). Unicode fallbacks (Windows Alt+numpad, Linux Ctrl+Shift+U) are on the roadmap.
- Typing speed is bounded by the console: a few hundred characters per second at most.
- OCR reads pixels; it cannot know whether a glyph is `0` or `O`. Always review.
- The `de` layout's AltGr and dead-key handling has had less testing than `us`; reports welcome.

## Roadmap

1. Verify the Windows and macOS backends on real machines (run `dcdclip --check` first, it
   prints what the backend sees without typing anything).
2. Unicode fallbacks for characters missing on the guest layout.
3. Named profiles per VM (e.g. "Windows DE", "Linux US").
4. Second OCR engine (RapidOCR) if Tesseract's error rate is too high on GUI screens.

### Diagnostics

`dcdclip --check` prints the platform backends, permission notes and the windows it can see,
without starting the GUI or sending a single key. Include its output in bug reports.

## Development

```bash
pip install -e ".[dev]"
pytest -q                      # unit tests, no display needed
ruff check . && ruff format .
pip install -e ".[build]" && pyinstaller --clean --noconfirm packaging/dcdclip.spec   # -> dist/
```

CI runs lint and tests on Linux, Windows and macOS. Pushing a tag `v*` builds the portable
archives for all three platforms and attaches them to a GitHub release (a pre-release when the
tag contains `-rc`, `-beta` or `-alpha`). Bump the version in `pyproject.toml` and
`dcdclip/__init__.py` first.

## Contributing

Issues and pull requests are welcome, especially:

- keyboard layout tables for other languages,
- reports from other VM images (which layout, what came out wrong),
- the Windows and macOS backends.

## License

MIT, see [`LICENSE`](LICENSE). Dependencies keep their own licenses: PySide6/Qt (LGPL v3),
python-xlib (LGPL), mss (MIT), Pillow (MIT-CMU), pytesseract (Apache 2.0); Tesseract itself
(Apache 2.0) is not bundled.
