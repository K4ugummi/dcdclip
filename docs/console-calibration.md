# Identifying the console client and calibrating the keyboard settings

## 1. Which client does the DCD Remote Console use?

Open the Remote Console tab in Firefox, press `F12`, then:

- **Network tab**, filter `JS`, reload the console page. Look for file names containing
  `novnc`, `rfb`, `keyboard`, `guacamole`, `spice` or `xterm`.
- **Console tab**: type `window.RFB` or `document.querySelector('canvas')` and press Enter.
  noVNC pages have a `<canvas>` inside a `<div id="noVNC_container">` or similar.
- **Inspector tab**: `Ctrl+F` and search for `noVNC` or `guac`.

Record the result in `CLAUDE.md` ("Decisions").

## 2. Calibration: keysym vs scancode transport

Log into a VM whose layout you know (e.g. a German Windows or `localectl` says `de`).
Open a text editor or a shell in the VM, focus the console and type on the **host**
keyboard, one key at a time:

| host key (German) | guest shows `keysym` transport (en-us server keymap) | guest shows `scancode` transport |
| --- | --- | --- |
| `z` | `y` | `z` |
| `-` | `ß` | `-` |
| `#` | `\` | `#` |
| `<` | `;` (or nothing) | `<` |

The column that matches is the transport to select in Settings.

**Worked example (Linux VM with `us` layout):** typing `ls -al` with the defaults of an early build (guest `de`,
transport `keysym`) produced `ls &al`. The tool had pressed Shift+Digit7 on the host (the
German key for `/`, which is the en-us keysym on the physical key where `de` has `-`).
The guest received the *physical* keys Shift+Digit7 and, with a US layout, printed `&`.
Conclusion: the DCD console forwards physical key codes (**`scancode` transport**, i.e.
noVNC with QEMU extended key events), and this VM has a **US** layout. The earlier
"z becomes y" observation is consistent with that (German host `z` key = physical KeyY).
Defaults are now transport `scancode`, guest layout `us`; pick `de` for German guests.

## 3. Verifying a guest layout profile

In Settings choose the guest layout and transport, then paste this line into the tool and
type it into a text editor in the VM:

```
az AZ 0-9 äöü ÄÖÜ ß ^ ` ´ ~ @ { } [ ] \ | < > " ' # + * / - _ , . ; : ! ? $ % & ( ) = €
```

Everything that comes back different from the input is either a layout data bug (fix
`dcdclip/keyboard/layouts.py`) or a transport limitation (document it here).

**Verified:** with transport `scancode` and guest layout `us`, the full line above (without the
umlauts, `ß` and `€`, which do not exist on `us`) comes through correctly on a Linux VM.
Still to verify: guest `de` (AltGr characters, dead keys, umlauts) on a German Windows VM.

Known limitations so far (unverified against the real console):

- `keysym` transport with the en-us server keymap cannot reach keys that do not exist on a
  US keyboard (`IntlBackslash`, i.e. `< > |` on a German guest). If the server keymap
  turns out to know scancode 0x56, add the key to the `us` layout as `("<", ">", "|")`.
- AltGr characters in `keysym` transport rely on the client forwarding the AltGr key press
  itself (noVNC does) and on the server applying it to the following scancode.
