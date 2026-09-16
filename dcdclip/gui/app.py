"""Application bootstrap."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox

from dcdclip.config import Settings
from dcdclip.platform import create_backends


def run(argv: list[str]) -> int:
    app = QApplication(argv)
    app.setApplicationName("dcdclip")
    app.setApplicationDisplayName("DCD Console Clipboard")
    try:
        backends = create_backends()
    except RuntimeError as exc:
        QMessageBox.critical(None, "dcdclip", str(exc))
        return 2

    from dcdclip.gui.main_window import MainWindow

    window = MainWindow(Settings.load(), backends)
    window.show()
    try:
        return app.exec()
    finally:
        backends.close()
