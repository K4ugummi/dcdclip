"""Main window: target window picker, paste-in tab, OCR tab, settings tab."""

from __future__ import annotations

import time

from PIL import Image
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from dcdclip.config import Settings
from dcdclip.gui.region_select import RegionSelector
from dcdclip.gui.workers import HotkeySignals, OcrWorker, TypeWorker
from dcdclip.keyboard.layouts import LAYOUTS, get_layout
from dcdclip.keyboard.planner import (
    IndentMode,
    NewlineMode,
    TabMode,
    Transport,
    TypeOptions,
    TypePlan,
    plan_text,
)
from dcdclip.ocr.capture import capture_rect
from dcdclip.ocr.engine import OcrOptions, default_engine
from dcdclip.ocr.preprocess import PreprocessOptions
from dcdclip.platform import Backends
from dcdclip.windows.base import Rect, WindowInfo, matches_filter


def _pil_to_pixmap(img: Image.Image) -> QPixmap:
    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, backends: Backends) -> None:
        super().__init__()
        self.settings = settings
        self.backends = backends
        self.ocr_engine = default_engine()
        self._type_worker: TypeWorker | None = None
        self._ocr_worker: OcrWorker | None = None
        self._countdown_left = 0
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._countdown_tick)
        self._last_capture: Image.Image | None = None
        self._last_region: Rect | None = None
        self._selector: RegionSelector | None = None
        self._hotkey_signals = HotkeySignals()
        self._hotkey_signals.type_requested.connect(self._hotkey_type)
        self._hotkey_signals.abort_requested.connect(self._abort_typing)

        self.setWindowTitle("DCD Console Clipboard")
        self.resize(760, 640)
        self._build_ui()
        self.refresh_windows()
        self._apply_hotkeys()

    # ------------------------------------------------------------------ UI construction
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        target_box = QGroupBox("Target browser window")
        target_row = QHBoxLayout(target_box)
        self.window_combo = QComboBox()
        self.window_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.window_combo.setMinimumContentsLength(40)
        self.filter_check = QCheckBox("Only console-like windows")
        self.filter_check.setChecked(True)
        self.filter_check.toggled.connect(self.refresh_windows)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_windows)
        target_row.addWidget(self.window_combo, 1)
        target_row.addWidget(self.filter_check)
        target_row.addWidget(refresh)
        root.addWidget(target_box)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_paste_tab(), "Paste into console")
        self.tabs.addTab(self._build_ocr_tab(), "Copy from console (OCR)")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        root.addWidget(self.tabs, 1)

        self.status = QLabel("Ready.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.setCentralWidget(central)

    def _build_paste_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Text to type into the VM (never stored on disk):"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Paste commands, passwords, key files ...")
        self.text_edit.textChanged.connect(self._update_plan_preview)
        layout.addWidget(self.text_edit, 1)

        self.plan_label = QLabel("")
        self.plan_label.setWordWrap(True)
        layout.addWidget(self.plan_label)

        row = QHBoxLayout()
        row.addWidget(QLabel("Countdown (s):"))
        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(0, 15)
        self.countdown_spin.setValue(self.settings.countdown_s)
        self.countdown_spin.valueChanged.connect(self._save_from_widgets)
        row.addWidget(self.countdown_spin)
        self.clear_check = QCheckBox("Clear text after typing")
        self.clear_check.setChecked(self.settings.clear_after_typing)
        self.clear_check.toggled.connect(self._save_from_widgets)
        row.addWidget(self.clear_check)
        self.trailing_newline_check = QCheckBox("Press Enter at the end")
        row.addWidget(self.trailing_newline_check)
        row.addStretch(1)
        self.type_button = QPushButton("Type into console")
        self.type_button.setDefault(True)
        self.type_button.clicked.connect(self.start_typing)
        row.addWidget(self.type_button)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self._abort_typing)
        row.addWidget(self.abort_button)
        layout.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        return tab

    def _build_ocr_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        self.capture_window_button = QPushButton("Capture target window")
        self.capture_window_button.clicked.connect(self.capture_target_window)
        row.addWidget(self.capture_window_button)
        self.capture_region_button = QPushButton("Select screen region…")
        self.capture_region_button.clicked.connect(self.capture_region)
        row.addWidget(self.capture_region_button)
        self.recapture_button = QPushButton("Capture last region again")
        self.recapture_button.setEnabled(False)
        self.recapture_button.clicked.connect(self.capture_last_region)
        row.addWidget(self.recapture_button)
        self.rerun_button = QPushButton("Run OCR again")
        self.rerun_button.setEnabled(False)
        self.rerun_button.clicked.connect(self._run_ocr_on_last)
        row.addWidget(self.rerun_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.preview = QLabel("No capture yet.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(140)
        self.preview.setStyleSheet("background: #333; color: #ccc;")
        layout.addWidget(self.preview)

        layout.addWidget(QLabel("Recognised text (edit before copying):"))
        self.ocr_text = QPlainTextEdit()
        layout.addWidget(self.ocr_text, 1)

        row2 = QHBoxLayout()
        self.auto_copy_check = QCheckBox("Copy automatically after OCR")
        self.auto_copy_check.setChecked(self.settings.ocr_auto_copy)
        self.auto_copy_check.toggled.connect(self._save_from_widgets)
        row2.addWidget(self.auto_copy_check)
        row2.addStretch(1)
        copy = QPushButton("Copy to clipboard")
        copy.clicked.connect(self._copy_ocr_text)
        row2.addWidget(copy)
        layout.addLayout(row2)

        ok, info = self.ocr_engine.available()
        self.ocr_status = QLabel(("OCR engine: " if ok else "OCR unavailable: ") + info)
        self.ocr_status.setWordWrap(True)
        layout.addWidget(self.ocr_status)
        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        s = self.settings

        self.layout_combo = QComboBox()
        for name, layout in LAYOUTS.items():
            self.layout_combo.addItem(f"{name} - {layout.description}", name)
        self._select_data(self.layout_combo, s.guest_layout)
        form.addRow("Guest (VM) keyboard layout", self.layout_combo)

        self.transport_combo = QComboBox()
        self.transport_combo.addItem(
            "keysym (browser sends key symbols; en-us server keymap)", "keysym"
        )
        self.transport_combo.addItem("scancode (browser sends physical key codes)", "scancode")
        self._select_data(self.transport_combo, s.transport)
        form.addRow("Console transport", self.transport_combo)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(2, 500)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(s.delay_ms)
        form.addRow("Delay per key", self.delay_spin)

        self.newline_combo = QComboBox()
        for mode, label in (
            ("enter", "Enter"),
            ("shift_enter", "Shift+Enter"),
            ("ctrl_enter", "Ctrl+Enter"),
        ):
            self.newline_combo.addItem(label, mode)
        self._select_data(self.newline_combo, s.newline)
        form.addRow("Newline as", self.newline_combo)

        self.tab_combo = QComboBox()
        self.tab_combo.addItem("Tab key", "tab")
        self.tab_combo.addItem("Spaces", "spaces")
        self._select_data(self.tab_combo, s.tab)
        self.tab_spaces_spin = QSpinBox()
        self.tab_spaces_spin.setRange(1, 16)
        self.tab_spaces_spin.setValue(s.tab_spaces)
        tab_row = QHBoxLayout()
        tab_row.addWidget(self.tab_combo)
        tab_row.addWidget(QLabel("spaces per tab:"))
        tab_row.addWidget(self.tab_spaces_spin)
        form.addRow("Tab characters", tab_row)

        self.indent_combo = QComboBox()
        self.indent_combo.addItem("keep as is", "keep")
        self.indent_combo.addItem("remove common indentation", "common")
        self.indent_combo.addItem("strip all leading whitespace", "strip")
        self._select_data(self.indent_combo, s.indent)
        form.addRow("Indentation", self.indent_combo)

        self.activate_delay_spin = QSpinBox()
        self.activate_delay_spin.setRange(0, 5000)
        self.activate_delay_spin.setSuffix(" ms")
        self.activate_delay_spin.setValue(s.activate_delay_ms)
        form.addRow("Wait after focusing window", self.activate_delay_spin)

        self.hotkeys_check = QCheckBox("Enable global hotkeys")
        self.hotkeys_check.setChecked(s.hotkeys_enabled)
        form.addRow(self.hotkeys_check)
        self.hotkey_type_edit = QLineEdit(s.hotkey_type)
        form.addRow("Hotkey: type now (no countdown)", self.hotkey_type_edit)
        self.hotkey_abort_edit = QLineEdit(s.hotkey_abort)
        form.addRow("Hotkey: abort typing", self.hotkey_abort_edit)

        self.title_filter_edit = QLineEdit(s.window_title_filter)
        form.addRow("Window title filter", self.title_filter_edit)

        self.ocr_lang_edit = QLineEdit(s.ocr_lang)
        form.addRow("OCR languages (tesseract, e.g. eng or deu+eng)", self.ocr_lang_edit)
        self.ocr_psm_spin = QSpinBox()
        self.ocr_psm_spin.setRange(0, 13)
        self.ocr_psm_spin.setValue(s.ocr_psm)
        form.addRow("OCR page segmentation mode (6 = block)", self.ocr_psm_spin)
        self.ocr_scale_spin = QSpinBox()
        self.ocr_scale_spin.setRange(1, 6)
        self.ocr_scale_spin.setValue(s.ocr_scale)
        form.addRow("OCR upscale factor", self.ocr_scale_spin)
        self.ocr_threshold_check = QCheckBox("Binarise image before OCR (try if results are poor)")
        self.ocr_threshold_check.setChecked(s.ocr_threshold)
        form.addRow(self.ocr_threshold_check)
        self.ocr_cleanup_check = QCheckBox("Normalise quotes/dashes to ASCII in OCR result")
        self.ocr_cleanup_check.setChecked(s.ocr_cleanup)
        form.addRow(self.ocr_cleanup_check)

        for w in (
            self.layout_combo,
            self.transport_combo,
            self.newline_combo,
            self.tab_combo,
            self.indent_combo,
        ):
            w.currentIndexChanged.connect(self._save_from_widgets)
        for w in (
            self.delay_spin,
            self.tab_spaces_spin,
            self.activate_delay_spin,
            self.ocr_psm_spin,
            self.ocr_scale_spin,
        ):
            w.valueChanged.connect(self._save_from_widgets)
        for w in (
            self.hotkey_type_edit,
            self.hotkey_abort_edit,
            self.title_filter_edit,
            self.ocr_lang_edit,
        ):
            w.editingFinished.connect(self._save_from_widgets)
        self.hotkeys_check.toggled.connect(self._save_from_widgets)
        self.ocr_threshold_check.toggled.connect(self._save_from_widgets)
        self.ocr_cleanup_check.toggled.connect(self._save_from_widgets)
        return tab

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    # ------------------------------------------------------------------ settings
    def _save_from_widgets(self) -> None:
        s = self.settings
        s.guest_layout = self.layout_combo.currentData()
        s.transport = self.transport_combo.currentData()
        s.delay_ms = self.delay_spin.value()
        s.newline = self.newline_combo.currentData()
        s.tab = self.tab_combo.currentData()
        s.tab_spaces = self.tab_spaces_spin.value()
        s.indent = self.indent_combo.currentData()
        s.activate_delay_ms = self.activate_delay_spin.value()
        s.countdown_s = self.countdown_spin.value()
        s.clear_after_typing = self.clear_check.isChecked()
        hotkeys_changed = (
            s.hotkeys_enabled != self.hotkeys_check.isChecked()
            or s.hotkey_type != self.hotkey_type_edit.text().strip()
            or s.hotkey_abort != self.hotkey_abort_edit.text().strip()
        )
        s.hotkeys_enabled = self.hotkeys_check.isChecked()
        s.hotkey_type = self.hotkey_type_edit.text().strip()
        s.hotkey_abort = self.hotkey_abort_edit.text().strip()
        filter_changed = s.window_title_filter != self.title_filter_edit.text().strip()
        s.window_title_filter = self.title_filter_edit.text().strip()
        s.ocr_lang = self.ocr_lang_edit.text().strip() or "eng"
        s.ocr_psm = self.ocr_psm_spin.value()
        s.ocr_scale = self.ocr_scale_spin.value()
        s.ocr_threshold = self.ocr_threshold_check.isChecked()
        s.ocr_cleanup = self.ocr_cleanup_check.isChecked()
        s.ocr_auto_copy = self.auto_copy_check.isChecked()
        try:
            s.save()
        except OSError as exc:
            self._set_status(f"Could not save settings: {exc}")
        if hotkeys_changed:
            self._apply_hotkeys()
        if filter_changed:
            self.refresh_windows()
        self._update_plan_preview()

    def _type_options(self) -> TypeOptions:
        s = self.settings
        return TypeOptions(
            transport=Transport(s.transport),
            newline=NewlineMode(s.newline),
            tab=TabMode(s.tab),
            tab_spaces=s.tab_spaces,
            indent=IndentMode(s.indent),
            trailing_newline=self.trailing_newline_check.isChecked(),
        )

    def _apply_hotkeys(self) -> None:
        hk = self.backends.hotkeys
        if hk is None:
            return
        try:
            hk.unbind_all()
            if self.settings.hotkeys_enabled:
                if self.settings.hotkey_type:
                    hk.bind(self.settings.hotkey_type, self._hotkey_signals.type_requested.emit)
                if self.settings.hotkey_abort:
                    hk.bind(self.settings.hotkey_abort, self._hotkey_signals.abort_requested.emit)
            hk.start()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Hotkeys not active: {exc}")

    # ------------------------------------------------------------------ windows
    def refresh_windows(self) -> None:
        current = self.window_combo.currentData()
        try:
            wins = self.backends.windows.list_windows()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Cannot list windows: {exc}")
            return
        own = int(self.winId())
        wins = [w for w in wins if w.id != own and w.title]
        if self.filter_check.isChecked():
            filtered = [
                w
                for w in wins
                if matches_filter(
                    w, self.settings.window_title_filter, tuple(self.settings.window_classes)
                )
            ]
            wins = filtered or wins
        self.window_combo.blockSignals(True)
        self.window_combo.clear()
        for w in wins:
            self.window_combo.addItem(w.label(), w.id)
        self.window_combo.blockSignals(False)
        if current is not None:
            self._select_data(self.window_combo, current)
        self._update_plan_preview()

    def _target(self) -> WindowInfo | None:
        wid = self.window_combo.currentData()
        if wid is None:
            return None
        return WindowInfo(int(wid), self.window_combo.currentText(), "")

    # ------------------------------------------------------------------ typing
    def _current_plan(self) -> TypePlan:
        return plan_text(
            self.text_edit.toPlainText(),
            get_layout(self.settings.guest_layout),
            get_layout(self.settings.server_layout),
            self._type_options(),
        )

    def _update_plan_preview(self) -> None:
        text = self.text_edit.toPlainText()
        if not text:
            self.plan_label.setText("")
            return
        plan = self._current_plan()
        est = plan.taps * self.settings.delay_ms / 1000
        msg = f"{plan.taps} key presses, about {est:.1f} s."
        if plan.unsupported:
            chars = " ".join(repr(c) for c in plan.unsupported)
            msg += f"  Not typeable with this layout/transport and will be skipped: {chars}"
        self.plan_label.setText(msg)

    def start_typing(self) -> None:
        if self._type_worker is not None or self._countdown.isActive():
            return
        target = self._target()
        if target is None:
            self._set_status("Select a target window first.")
            return
        plan = self._current_plan()
        if plan.taps == 0:
            self._set_status("Nothing to type.")
            return
        if plan.unsupported:
            chars = " ".join(repr(c) for c in plan.unsupported)
            answer = QMessageBox.question(
                self,
                "Unsupported characters",
                f"These characters cannot be typed with the current guest layout and "
                f"transport and will be skipped:\n{chars}\n\nContinue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._pending_plan = plan
        self._pending_target = target.id
        self._countdown_left = self.countdown_spin.value()
        self._set_typing_ui(True)
        if self._countdown_left > 0:
            self._countdown_tick(first=True)
            self._countdown.start()
        else:
            self._focus_and_type()

    def _countdown_tick(self, first: bool = False) -> None:
        if not first:
            self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._countdown.stop()
            self._focus_and_type()
            return
        self.type_button.setText(f"Typing in {self._countdown_left}…")
        self._set_status("Countdown running. Abort to cancel.")

    def _focus_and_type(self) -> None:
        self.type_button.setText("Focusing window…")
        try:
            self.backends.windows.activate(self._pending_target)
        except Exception as exc:  # noqa: BLE001
            self._typing_failed(f"Could not focus target window: {exc}")
            return
        QTimer.singleShot(self.settings.activate_delay_ms, self._start_worker)

    def _start_worker(self) -> None:
        if self._type_worker is not None:
            return
        self.type_button.setText("Typing…")
        self.progress.setRange(0, max(self._pending_plan.taps, 1))
        self.progress.setValue(0)
        worker = TypeWorker(
            self._pending_plan,
            self.backends.keyboard,
            self.backends.windows,
            self._pending_target,
            self.settings.delay_ms / 1000,
        )
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._typing_done)
        worker.failed.connect(self._typing_failed)
        self._type_worker = worker
        worker.start()

    def _hotkey_type(self) -> None:
        """Hotkey: type immediately; if the target is not focused, focus it first."""
        if self._type_worker is not None or self._countdown.isActive():
            return
        target = self._target()
        if target is None:
            return
        plan = self._current_plan()
        if plan.taps == 0:
            return
        self._pending_plan = plan
        self._pending_target = target.id
        self._set_typing_ui(True)
        if self.backends.windows.active_window_id() == target.id:
            self._start_worker()
        else:
            self._focus_and_type()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(done)
        self._set_status(f"Typing… {done}/{total}")

    def _typing_done(self, message: str) -> None:
        self._finish_typing(message)
        if self.clear_check.isChecked():
            self.text_edit.clear()

    def _typing_failed(self, message: str) -> None:
        self._finish_typing(message)

    def _finish_typing(self, message: str) -> None:
        self._countdown.stop()
        if self._type_worker is not None:
            self._type_worker.wait(2000)
            self._type_worker = None
        self._set_typing_ui(False)
        self._set_status(message)

    def _abort_typing(self) -> None:
        if self._countdown.isActive():
            self._countdown.stop()
            self._set_typing_ui(False)
            self._set_status("Countdown cancelled.")
            return
        if self._type_worker is not None:
            self._type_worker.abort()

    def _set_typing_ui(self, typing: bool) -> None:
        self.type_button.setEnabled(not typing)
        self.abort_button.setEnabled(typing)
        self.text_edit.setReadOnly(typing)
        if not typing:
            self.type_button.setText("Type into console")

    # ------------------------------------------------------------------ OCR
    def capture_target_window(self) -> None:
        target = self._target()
        if target is None:
            self._set_status("Select a target window first.")
            return
        rect = self.backends.windows.geometry(target.id)
        if rect is None:
            self._set_status("Target window is gone; refresh the list.")
            return
        self.backends.windows.activate(target.id)
        QTimer.singleShot(
            max(self.settings.activate_delay_ms, 200), lambda: self._capture_and_ocr(rect)
        )

    def capture_region(self) -> None:
        self.hide()
        self._selector = RegionSelector()
        self._selector.selected.connect(self._region_selected)
        self._selector.cancelled.connect(self._region_cancelled)
        QTimer.singleShot(200, self._selector.show)

    def _region_selected(self, rect: QRect) -> None:
        self._selector = None
        self._last_region = Rect(rect.x(), rect.y(), rect.width(), rect.height())
        self.recapture_button.setEnabled(True)
        QTimer.singleShot(150, lambda: self._capture_and_ocr(self._last_region))

    def capture_last_region(self) -> None:
        if self._last_region is None:
            return
        self.hide()
        QTimer.singleShot(250, lambda: self._capture_and_ocr(self._last_region))

    def _region_cancelled(self) -> None:
        self._selector = None
        self.show()
        self.activateWindow()
        self._set_status("Region selection cancelled.")

    def _capture_and_ocr(self, rect: Rect) -> None:
        try:
            self._last_capture = capture_rect(rect)
        except Exception as exc:  # noqa: BLE001
            self.show()
            self.activateWindow()
            self._set_status(f"Capture failed: {exc}")
            return
        self.show()
        self.activateWindow()
        self.raise_()
        self.rerun_button.setEnabled(True)
        self._run_ocr_on_last()

    def _run_ocr_on_last(self) -> None:
        if self._last_capture is None or self._ocr_worker is not None:
            return
        ok, info = self.ocr_engine.available()
        self.preview.setPixmap(
            _pil_to_pixmap(self._last_capture).scaled(
                self.preview.width(),
                max(self.preview.height(), 140),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        if not ok:
            self._set_status(f"Captured, but OCR unavailable: {info}")
            return
        self._set_status("Running OCR…")
        worker = OcrWorker(
            self._last_capture,
            self.ocr_engine,
            OcrOptions(lang=self.settings.ocr_lang, psm=self.settings.ocr_psm),
            PreprocessOptions(scale=self.settings.ocr_scale, threshold=self.settings.ocr_threshold),
            cleanup=self.settings.ocr_cleanup,
        )
        worker.succeeded.connect(self._ocr_done)
        worker.failed.connect(self._ocr_failed)
        self._ocr_worker = worker
        worker.start()

    def _ocr_done(self, text: str, _processed: object) -> None:
        self._ocr_worker = None
        self.ocr_text.setPlainText(text)
        lines = text.count("\n") + 1 if text else 0
        self._set_status(f"OCR finished: {lines} lines.")
        if self.auto_copy_check.isChecked() and text:
            self._copy_ocr_text()

    def _ocr_failed(self, message: str) -> None:
        self._ocr_worker = None
        self._set_status(f"OCR failed: {message}")

    def _copy_ocr_text(self) -> None:
        text = self.ocr_text.toPlainText()
        QApplication.clipboard().setText(text)
        self._set_status(f"Copied {len(text)} characters to the clipboard.")

    # ------------------------------------------------------------------ misc
    def _set_status(self, message: str) -> None:
        self.status.setText(f"{time.strftime('%H:%M:%S')}  {message}")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._type_worker is not None:
            self._type_worker.abort()
            self._type_worker.wait(2000)
        super().closeEvent(event)
