"""Background threads for typing and OCR so the GUI stays responsive."""

from __future__ import annotations

import time

from PIL import Image
from PySide6.QtCore import QObject, QThread, Signal

from dcdclip.keyboard.backend import KeyboardBackend
from dcdclip.keyboard.planner import KeyTap, TypePlan
from dcdclip.ocr.cleanup import normalise_console_text
from dcdclip.ocr.engine import OcrEngine, OcrOptions
from dcdclip.ocr.preprocess import PreprocessOptions, preprocess
from dcdclip.windows.base import WindowBackend


class HotkeySignals(QObject):
    """Bridge from the hotkey listener thread into the Qt event loop."""

    type_requested = Signal()
    abort_requested = Signal()


class TypeWorker(QThread):
    progress = Signal(int, int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        plan: TypePlan,
        keyboard: KeyboardBackend,
        windows: WindowBackend,
        target_id: int,
        delay_s: float,
    ) -> None:
        super().__init__()
        self._taps = [s for s in plan.steps if isinstance(s, KeyTap)]
        self._keyboard = keyboard
        self._windows = windows
        self._target = target_id
        self._delay = max(delay_s, 0.002)
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        total = len(self._taps)
        done = 0
        try:
            for tap in self._taps:
                if self._abort:
                    self.failed.emit(f"Aborted after {done} of {total} keys.")
                    return
                if self._windows.active_window_id() != self._target:
                    self.failed.emit(
                        f"Target window lost focus; stopped after {done} of {total} keys."
                    )
                    return
                self._keyboard.tap(tap, hold_s=self._delay / 2)
                time.sleep(self._delay / 2)
                done += 1
                self.progress.emit(done, total)
            self.succeeded.emit(f"Typed {total} keys.")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Error after {done} of {total} keys: {exc}")
        finally:
            self._keyboard.release_all()


class OcrWorker(QThread):
    succeeded = Signal(str, object)  # text, preprocessed PIL image
    failed = Signal(str)

    def __init__(
        self,
        image: Image.Image,
        engine: OcrEngine,
        ocr_opts: OcrOptions,
        pre_opts: PreprocessOptions,
        cleanup: bool = True,
    ) -> None:
        super().__init__()
        self._image = image
        self._engine = engine
        self._ocr_opts = ocr_opts
        self._pre_opts = pre_opts
        self._cleanup = cleanup

    def run(self) -> None:
        try:
            processed = preprocess(self._image, self._pre_opts)
            text = self._engine.recognize(processed, self._ocr_opts)
            if self._cleanup:
                text = normalise_console_text(text)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(text, processed)
