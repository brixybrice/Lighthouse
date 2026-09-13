"""Rolling lux strip-chart with a graduated y-axis.

Plain QPainter, no plotting dependency — this app is small enough not to
need pyqtgraph. Graphs the raw lux reading (not EV/f-stop): those also move
whenever ISO/ND/shutter change, which would show up as discontinuities
that look like sensor noise but aren't.

Supports drawing several series at once (used by AveragePanel: each
sensor's raw curve dim, the average bold) sharing one y-axis scale.

The x-axis right edge is always "now" (wall-clock time), not the last
sample's timestamp — repainted on a fast timer from MainWindow independent
of how often actual UDP readings arrive (~2Hz), so the whole chart scrolls
smoothly in real time instead of visibly jumping once per reading. Same
idea as Semaphore's animated spectrum curve (see its CLAUDE.md), applied
to a scrolling chart instead of a per-sweep curve.
"""

import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from lighthouse.core.history import SampleHistory
from lighthouse.ui.theme import BORDER, STATUS_OK, TEXT_DIM

GRID_LINES = 3
MARGIN = 4
DEFAULT_WINDOW_SECONDS = 30.0


@dataclass
class GraphSeries:
    history: SampleHistory
    color: str
    width: int = 2


class LuxGraphWidget(QWidget):
    def __init__(self, series: SampleHistory | list[GraphSeries], parent=None):
        super().__init__(parent)
        self._series: list[GraphSeries] = self._normalize(series)
        self.setMinimumHeight(64)

    @staticmethod
    def _normalize(series: SampleHistory | list[GraphSeries]) -> list[GraphSeries]:
        if isinstance(series, SampleHistory):
            return [GraphSeries(series, STATUS_OK, 2)]
        return list(series)

    def set_series(self, series: SampleHistory | list[GraphSeries]) -> None:
        self._series = self._normalize(series)
        self.update()

    def _combined_bounds(self) -> tuple[float, float] | None:
        values: list[float] = []
        for s in self._series:
            bounds = s.history.bounds()
            if bounds is not None:
                values.extend(bounds)
        if not values:
            return None
        return min(values), max(values)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

        bounds = self._combined_bounds()
        if bounds is None:
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for data…")
            painter.end()
            return

        lo, hi = bounds
        if hi - lo < 1e-6:
            lo, hi = lo - 1, hi + 1  # keep a degenerate flat reading paintable

        window_seconds = max((s.history.window_seconds for s in self._series), default=DEFAULT_WINDOW_SECONDS)
        t1 = time.monotonic()
        t0 = t1 - window_seconds

        def to_point(ts: float, value: float) -> QPointF:
            x = rect.left() + (ts - t0) / window_seconds * rect.width()
            y = rect.bottom() - (value - lo) / (hi - lo) * rect.height()
            return QPointF(x, y)

        grid_pen = QPen(QColor(BORDER), 1, Qt.PenStyle.DotLine)
        for i in range(GRID_LINES + 1):
            y = rect.top() + i * rect.height() / GRID_LINES
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            value = hi - i * (hi - lo) / GRID_LINES
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(rect.left() + 2, int(y) - 2, f"{value:.1f}")

        for s in self._series:
            samples = s.history.samples
            if len(samples) < 2:
                continue
            painter.setPen(QPen(QColor(s.color), s.width))
            points = [to_point(ts, v) for ts, v in samples]
            for p1, p2 in zip(points, points[1:]):
                painter.drawLine(p1, p2)

        painter.end()
