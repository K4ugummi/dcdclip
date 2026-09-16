"""Full-screen translucent overlay to pick a screen rectangle with the mouse."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
    selected = Signal(QRect)  # in global (screen) coordinates
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        geo = QRect()
        for screen in QGuiApplication.screens():
            geo = geo.united(screen.geometry())
        self.setGeometry(geo)
        self._start: QPoint | None = None
        self._current: QPoint | None = None

    def _rect(self) -> QRect | None:
        if self._start is None or self._current is None:
            return None
        return QRect(self._start, self._current).normalized()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        rect = self._rect()
        if rect:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(255, 140, 0), 2))
            painter.drawRect(rect)
            painter.drawText(rect.topLeft() + QPoint(4, -6), f"{rect.width()} x {rect.height()}")
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = self._current = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._start is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        self._current = event.position().toPoint()
        rect = self._rect()
        self.close()
        if rect and rect.width() > 3 and rect.height() > 3:
            self.selected.emit(rect.translated(self.geometry().topLeft()))
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()
