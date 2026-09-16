# PyInstaller spec: `pyinstaller --clean --noconfirm packaging/dcdclip.spec`
# Produces dist/dcdclip/ (Linux, Windows) or dist/dcdclip.app (macOS).
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 - SPECPATH is injected

hiddenimports = ["pytesseract", "mss"]
if sys.platform.startswith("linux"):
    hiddenimports += collect_submodules("Xlib")

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "dcdclip", "__main__.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtMultimedia",
        "PySide6.QtCharts",
        "PySide6.Qt3DCore",
        "PySide6.QtPdf",
        "PySide6.QtBluetooth",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="dcdclip",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="dcdclip")  # noqa: F821
if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="dcdclip.app",
        bundle_identifier="io.github.k4ugummi.dcdclip",
        info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "12.0"},
    )
