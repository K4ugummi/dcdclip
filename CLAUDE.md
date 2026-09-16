# IONOS DCD Console Clipboard Tool (dcdclip)

Desktop tool that works around the missing clipboard in the IONOS DCD (Data Center
Designer) browser "Remote Console" (an HTML5, VNC-style session to a Windows or Linux VM).

- **Host -> VM ("paste in")**: the user pastes text into the tool, the tool focuses the
  browser window with the console and *types* the text by emulating key presses, aware of
  the VM's keyboard layout.
- **VM -> Host ("copy out")**: the tool screenshots the console (whole window or a
  user-drawn region), runs OCR and lets the user review/edit before copying to the host
  clipboard.

Typical payloads: bash command lines, passwords, SSH key file contents. Treat all typed
text as secret: never log it, never persist it, clear it after typing (default on).

## Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Language | Python 3.12 | Fastest iteration; best library coverage for input emulation, screenshots and OCR on all three target platforms. Rust/.NET/Node rejected: weaker or unmaintained input/OCR bindings. |
| GUI | PySide6 (Qt 6) | Cross-platform (Linux, macOS, Windows are all required), proper text widgets, translucent overlay for region selection, tray/hotkey friendly. Tkinter is not even installed on the dev host. |
| Windows/focus (Linux) | `python-xlib` + EWMH | No subprocess, already installed. `wmctrl -lx` for manual checks. |
| Key emulation (Linux) | X11 XTEST via `python-xlib`, fixed evdev keycodes, host keymap lookup, temporary spare-keycode remap for keysyms the host layout lacks | Exact keycode/modifier/timing control. `xdotool type` and `pynput` are not used: they only do the remap trick and cannot press a *physical* key, which the scancode transport needs. |
| Screenshot | `mss` + Pillow | Fast, cross-platform. |
| OCR | Tesseract 5 via `pytesseract` behind an `OcrEngine` interface | Offline, proven on monospace text. User has no preference; if accuracy on GUI screens is poor, add RapidOCR (pip-only ONNX, easier to ship on macOS/Windows) as a second engine. |
| Packaging | `pyproject.toml` (setuptools), venv in `.venv/`, `uv` for installs | The dev host lacks `python3-venv` and blocks `pip --user` (PEP 668); the standalone `uv` in `~/.local/bin` sidesteps both. |
| Quality | `ruff` (lint+format, line length 100), `pytest`, `mypy` (lenient) | Layout/planner logic is unit-tested without an X server. |
| Platforms | Linux/X11 first (dev host: Cinnamon on X11, host layout `de`), then Windows and macOS | Required by the user. All OS-specific code sits behind `KeyboardBackend` / `WindowBackend` protocols; `dcdclip/platform.py` selects the backend. Wayland is not planned (would need uinput). |
| License | MIT (`LICENSE`), repo public | User wants open source; MIT is the simplest permissive option and compatible with PySide6 (LGPL). |
| Browser extension | No | Rejected by the user; the tool must stay an OS-level application. |
| Guest OSes | Windows and Linux (RHEL family, Ubuntu). | Layout differs per VM; select the guest layout per VM. |
| Console transport | **`scancode`** (the console forwards physical keys, see `docs/console-calibration.md`) | Default profile: transport `scancode`, guest layout `us`. The `keysym` transport stays available for other consoles. |
| Trigger | Button with countdown **and** configurable global hotkeys (type now / abort) | User request. Hotkeys are X11 `XGrabKey` on Linux. |
| UI language | English | User request. Code, comments, docs, commits in English too. |

## Layout

```
dcdclip/
  __main__.py            python -m dcdclip / `dcdclip` script -> gui.app.run
  config.py              Settings dataclass, JSON in ~/.config/dcdclip/config.json (never text)
  platform.py            create_backends(): picks X11 backends, raises on other platforms for now
  keyboard/
    model.py             Mod flags, KeyStroke, Layout (char <-> physical key+mods), keysym helpers
    layouts.py           guest layouts: us, de, de-nodeadkeys (data only, add more here)
    planner.py           text -> TypePlan of KeyTap/Unsupported; transports, newline/tab/indent policies
    backend.py           KeyboardBackend protocol
    backend_x11.py       XTEST implementation, evdev keycode table, spare-keycode remap
  windows/
    base.py              WindowInfo, Rect, WindowBackend protocol, matches_filter()
    x11.py               EWMH list/activate/geometry
    hotkeys_x11.py       XGrabKey listener thread, parse_hotkey("ctrl+alt+v")
  ocr/
    capture.py           mss region capture -> PIL
    preprocess.py        grayscale, auto-invert dark terminals, upscale, Otsu threshold
    engine.py            OcrEngine protocol, TesseractEngine
  gui/
    app.py               QApplication bootstrap
    main_window.py       target picker + tabs: paste-in, OCR, settings
    workers.py           TypeWorker / OcrWorker QThreads, HotkeySignals bridge
    region_select.py     full-screen overlay to drag a rectangle
tests/                   pure unit tests (layouts, planner, preprocessing, hotkey parsing)
docs/console-calibration.md   how to identify the console client and verify layout profiles
```

## Key technical facts

### The keyboard chain and the two transports

```
tool (XTEST) -> host X server (host layout de) -> browser -> VNC JS client
   -> VNC server (server keymap, assumed en-us) -> guest OS (guest layout)
```

- `Transport.SCANCODE` (default, matches the DCD console): the client forwards the
  physical key (`KeyboardEvent.code`). We press the physical key that the *guest layout*
  needs; the host layout is irrelevant. Consequence: the guest layout setting must match
  the VM exactly, otherwise e.g. `-` becomes `&`.
- `Transport.KEYSYM` (not used by the DCD console, kept for other VNC clients): the client forwards
  the keysym the host produced; the server maps it back to a scancode with its en-us keymap.
  We compute the en-us character on the physical key the guest layout needs and make the host
  emit that keysym (host keymap lookup, else temporary remap of spare keycode 248).
  AltGr characters: hold AltGr on the host and send the plain-level keysym via the remapped
  spare key (`KeyTap.force_remap`), so the host layout does not apply AltGr itself.
  Keys missing from a US keyboard (`IntlBackslash`: `< > |` on `de`) are unsupported in this
  transport until verified otherwise (`docs/console-calibration.md`).
- Dead keys (`^ ´ \`` on `de`) are typed as key + Space.
- Physical keys use W3C `KeyboardEvent.code` names everywhere; X11 keycodes are evdev+8
  (`backend_x11.X11_KEYCODES`). Verified against the dev host keymap on 2026-09-16.
- Verified end to end 2026-09-16 by typing into a local Qt window (not yet against the real
  DCD console): keysym transport for guest `de` produced the expected en-us keysyms, scancode
  transport pressed the expected physical keys, AltGr trick delivered the plain keysym.

### Focus and safety

- Activate with `_NET_ACTIVE_WINDOW` (Cinnamon honours it), wait `activate_delay_ms`, then
  type in a worker thread. Before **every** key the worker checks the active window is still
  the target and stops otherwise. Abort via button or hotkey; `release_all()` always runs.
- Default target filter: WM_CLASS contains firefox/chrome/chromium and title contains
  "Remote Console" (observed Firefox tab title). The list can be un-filtered.
- Text is held only in the QPlainTextEdit and cleared after successful typing by default.

### OCR

- Preprocess: grayscale, invert if dark, upscale x2 (Lanczos); Otsu binarisation is
  optional and off by default (measured on a Linux text console: Tesseract's own
  binarisation kept `]#` and `--` intact more often). Tesseract `--psm 6`,
  `preserve_interword_spaces=1`, language default `eng` (`deu+eng` for German UIs).
- Text is rebuilt from Tesseract's word boxes (`engine.reconstruct_lines`), not from its
  plain text output: console output is monospace, so horizontal gaps become spaces (columns
  stay aligned) and vertical gaps become blank lines. Tesseract's own text put an empty line
  after every console line and lost table alignment.
- Post-process (`ocr/cleanup.py`): typographic quotes/dashes back to ASCII and 3-4 dash runs
  before a letter collapsed to `--`, because Tesseract reads `--system` as `—-system`.
- Typical remaining confusions on the console font: `[`/`C`, `]`/`1`/`J`, `0`/`o`, `l`/`1`,
  `/`/`7`. Users must review before pasting; OCR is a helper, not a clipboard.
- Full-window capture includes the browser chrome (URL bar with the console token); prefer
  region capture. "Capture last region again" repeats the previous rectangle. Result is
  shown for editing; auto-copy is opt-in. Windows hanging off the screen are clamped to
  the visible area (`capture.clamp_to_screen`).
- Captured images are never written to disk; keep only anonymised samples under
  `tests/data/` if regression tests need them.

## Development workflow

```bash
export PATH="$HOME/.local/bin:$PATH"           # uv lives here on the dev host
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m dcdclip                    # run the GUI
.venv/bin/pytest -q                            # unit tests, no X server needed
.venv/bin/ruff check . && .venv/bin/ruff format .
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu   # OCR (needs a password)
```

Manual checks: `wmctrl -lx` (windows), `xev -event keyboard` (host keycodes/keysyms),
`setxkbmap -query` (host layout). To test typing without touching a VM, target any local
text editor window from the picker (un-filter the list).

## Packaging and release

- `packaging/dcdclip.spec` (PyInstaller, onedir; `.app` bundle on macOS). Local build:
  `pyinstaller --clean --noconfirm packaging/dcdclip.spec`.
- `.github/workflows/ci.yml`: ruff + pytest on Linux, Windows, macOS for pushes/PRs to `main`.
- `.github/workflows/release.yml`: on tag `v*` builds Linux (ubuntu-22.04 for old glibc),
  Windows and macOS arm64 archives, smoke-tests `--version`, attaches them to a GitHub
  release (pre-release when the tag contains `-rc`/`-beta`/`-alpha`).
- Version lives in `pyproject.toml` **and** `dcdclip/__init__.py`; bump both, then tag.
- GitHub: `K4ugummi/dcdclip` (public, MIT license). `gh` is a portable binary in `~/.local/bin`; it is not
  logged in, use `GH_TOKEN` from the git credential store in-process when needed.
- Windows/macOS archives are placeholders until `KeyboardBackend`/`WindowBackend`
  implementations for those platforms exist (`platform.create_backends` raises a clear error).

## Status

- 2026-09-16: first vertical slice implemented (Linux/X11): window picker, typing with
  countdown/hotkeys/abort, layouts `us`/`de`/`de-nodeadkeys`, OCR tab with window/region
  capture, settings persistence. Unit tests green. The console uses physical key codes;
  defaults are `scancode`/`us`, and the full ASCII character table (section 3 of the
  calibration doc) types correctly with a `us` guest, including all Shift characters.
  Tesseract 5.3.4 (eng, deu) on the dev host; OCR takes about 2 s per capture and is
  readable with the confusions listed under "OCR".

## Next steps

1. Verify the character table on a German Windows VM with guest layout `de` (AltGr keys,
   dead keys `^ ´ \``, umlauts). `us` is verified.
2. OCR quality: try a Windows console (GUI fonts, `deu+eng`); consider RapidOCR as a
   second engine if Tesseract's letter/digit confusions are too frequent.
3. Unicode fallbacks for characters not on the guest layout (Windows Alt+numpad, Linux
   Ctrl+Shift+U), per guest-OS profile.
4. Windows backend (SendInput + win32gui) and macOS backend (Quartz CGEvent + Accessibility
   permission), then PyInstaller packaging.
5. Named profiles ("Windows DE", "Linux US") instead of single global settings.

## Public repo hygiene

Do not mention specific VMs, hostnames, customers or internal names anywhere in the repo
(README, docs, CLAUDE.md, commit messages, test data). Describe findings generically
("a Linux VM with `us` layout").

## Open questions

1. Which JS client does the console use exactly (noVNC version)? Behaviour says physical
   key codes are forwarded; DevTools check still useful for edge cases (dead keys, AltGr).
