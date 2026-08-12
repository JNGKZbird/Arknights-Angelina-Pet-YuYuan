# Widget components
from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QIcon
from PySide6.QtWidgets import QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QPlainTextEdit, QLineEdit, QWidget
from core import THEME_ORANGE, THEME_ORANGE_LIGHT, THEME_DARK_CARD, THEME_DARK_BORDER, THEME_DARK_TEXT, THEME_DARK_SUBTEXT, THEME_LIGHT_CARD, THEME_LIGHT_BORDER, THEME_LIGHT_TEXT, THEME_LIGHT_SUBTEXT, THEME_DARK_BG, THEME_LIGHT_BG, PAD
import os

class _CloseButton(QPushButton):
    def __init__(self, callback):
        super().__init__()
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(callback)
        self._hover = False
        self.setMouseTracking(True)

    def enterEvent(self, e):
        self._hover = True; self.update()

    def leaveEvent(self, e):
        self._hover = False; self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._hover:
            p.setBrush(QColor("#e81123"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect(), 6, 6)
            p.setPen(QColor(255, 255, 255))
        else:
            p.setPen(QColor(150, 150, 160))
        p.setPen(QPen(p.pen().color(), 2))
        m = 12
        p.drawLine(m, m, self.width() - m, self.height() - m)
        p.drawLine(self.width() - m, m, m, self.height() - m)
        p.end()

class _DragBar(QWidget):
    """Title bar that supports window dragging."""
    def __init__(self, title, close_callback):
        super().__init__()
        self._close = close_callback
        self._drag_pos = None
        self.setFixedHeight(40)
        self.setStyleSheet("background:palette(Window);border-bottom:1px solid palette(Mid);")

        bar = QHBoxLayout(self)
        bar.setContentsMargins(14, 0, 6, 0)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:13px;font-weight:600;border:none;background:transparent;")
        bar.addWidget(title_label)
        bar.addStretch()
        close_btn = _CloseButton(self._close)
        bar.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            w = self.window()
            w.move(w.x() + delta.x(), w.y() + delta.y())
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

def _frameless_title_bar(layout, title, close_callback):
    """Add a custom title bar with close button to a frameless window."""
    bar_widget = _DragBar(title, close_callback)
    layout.insertWidget(0, bar_widget)

class SubtitleWindow(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._lines = []
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_text)
        self.hide()

    def show_text(self, text, duration_ms):
        if not text:
            self.hide_text()
            return
        font_metrics = QFontMetrics(self.font())
        max_width = 420
        self._lines = self._wrap_text(font_metrics, text, max_width)
        width = 0
        for line in self._lines:
            width = max(width, font_metrics.horizontalAdvance(line))
        width = min(max_width, width) + 28
        height = len(self._lines) * font_metrics.height() + 20
        self.resize(width, height)
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

    def hide_text(self):
        self._hide_timer.stop()
        self._lines = []
        self.hide()

    @staticmethod
    def _wrap_text(font_metrics, text, max_width):
        lines = []
        current = ""
        for ch in text:
            candidate = current + ch
            if font_metrics.horizontalAdvance(candidate) > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        bg = QColor(18, 18, 26, 215)
        fg = QColor(255, 255, 255, 245)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(fg)
        font_metrics = QFontMetrics(self.font())
        y = 10 + font_metrics.ascent()
        for line in self._lines:
            painter.drawText(14, y, line)
            y += font_metrics.height()

class ChatInputWindow(QWidget):
    submitted = Signal(str)

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("给安洁莉娜的话")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("博士想说点什么……")
        self.edit.returnPressed.connect(self.send)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.send)
        row = QHBoxLayout()
        row.addWidget(self.edit, 1)
        row.addWidget(self.send_button)
        layout.addLayout(row)

    def send(self):
        if not self.send_button.isEnabled():
            return
        text = self.edit.text().strip()
        if not text:
            return
        self.submitted.emit(text)
        self.edit.clear()

    def set_busy(self, busy):
        self.send_button.setEnabled(not busy)

