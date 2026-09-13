"""A single sensor's display: live lux + graph, computed EV/f-stop, and a
connection-status dot. Pure display widget — all the exposure math and the
"is this sensor stale" decision live in the caller (main_window), this
class only renders whatever it's told.

Every panel is a fixed SQUARE_SIZE square, so multiple sensors line up
evenly regardless of label/address length (and so the Settings panel next
to them, built the same way, matches their size).

Deliberately a QFrame, not a QGroupBox: a QGroupBox's native title sits in
a margin reserved ABOVE its border, so the visibly bordered box ends up
shorter than it is wide even with setFixedSize(SQUARE_SIZE, SQUARE_SIZE) —
confirmed by screenshotting the running app, it visibly wasn't square. The
sensor name is rendered as a plain bold label inside instead, so the whole
fixed-size box is the border and nothing is reserved outside it.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from lighthouse.core.exposure import ExposureResult, format_fstop
from lighthouse.core.history import SampleHistory
from lighthouse.ui.graph_widget import LuxGraphWidget
from lighthouse.ui.theme import BORDER, STATUS_OK, STATUS_STALE, TEXT_DIM

GRAPH_WINDOW_SECONDS = 30.0
SQUARE_SIZE = 220
GRAPH_HEIGHT = 96


class SensorPanel(QFrame):
    def __init__(self, sensor_id: str, label: str, ip: str, port: int, parent=None):
        super().__init__(parent)
        self.sensor_id = sensor_id
        self.label = label
        self.last_lux: float | None = None
        self.last_seen: float | None = None
        self.last_fstop_text = "f/—"
        self.last_fstop_value: float | None = None
        self.is_stale = True
        self.history = SampleHistory(window_seconds=GRAPH_WINDOW_SECONDS)

        self.setFixedSize(SQUARE_SIZE, SQUARE_SIZE)
        self.setObjectName("SensorPanel")
        self.setStyleSheet(
            f"QFrame#SensorPanel {{ border: 1px solid {BORDER}; border-radius: 6px; padding: 6px; }}"
        )

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 16px;")

        self._name_label = QLabel(label)
        self._name_label.setStyleSheet("font-weight: bold;")

        self._address_label = QLabel(f"{ip} : {port}")
        self._address_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")

        self._lux_label = QLabel("— lux")
        self._lux_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self._ev_label = QLabel("EV —")
        self._ev_label.setStyleSheet(f"color: {TEXT_DIM};")

        self._fstop_label = QLabel("f/—")
        self._fstop_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        self._fstop_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._graph = LuxGraphWidget(self.history)
        self._graph.setFixedHeight(GRAPH_HEIGHT)

        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(self._status_dot)
        name_row.addWidget(self._name_label)
        name_row.addStretch(1)

        readout_row = QHBoxLayout()
        readout_row.setSpacing(8)
        values_col = QVBoxLayout()
        values_col.setSpacing(0)
        values_col.addWidget(self._lux_label)
        values_col.addWidget(self._ev_label)
        readout_row.addLayout(values_col)
        readout_row.addStretch(1)
        readout_row.addWidget(self._fstop_label)

        layout = QVBoxLayout()
        layout.setSpacing(6)  # breathing room around the readout row
        layout.addLayout(name_row)
        layout.addWidget(self._address_label)
        layout.addLayout(readout_row)
        layout.addStretch(1)  # pushes the graph down to the bottom edge
        layout.addWidget(self._graph)
        self.setLayout(layout)

    def set_reading(self, lux: float, timestamp: float) -> None:
        self.last_lux = lux
        self.last_seen = timestamp
        self.is_stale = False  # tick() would only confirm this up to 500ms later
        self._lux_label.setText(f"{lux:.2f} lux")
        self.history.add(timestamp, lux)
        self._graph.update()

    def set_exposure(self, result: ExposureResult | None) -> None:
        if result is None:
            self._ev_label.setText("EV —")
            self.last_fstop_value = None
            self.last_fstop_text = "f/—"
            self._fstop_label.setText(self.last_fstop_text)
            return
        self._ev_label.setText(f"EV {result.ev_effective:.2f}")
        self.last_fstop_value = result.fstop
        self.last_fstop_text = format_fstop(result.fstop)
        self._fstop_label.setText(self.last_fstop_text)

    def tick(self, now: float, stale_after_seconds: float) -> None:
        """Called periodically by MainWindow: ages out the graph history and
        refreshes the connection-status dot, independent of new readings."""
        self.history.trim(now)

        if self.last_seen is None:
            self.is_stale = True
            self._status_dot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 16px;")
            return
        age = now - self.last_seen
        self.is_stale = age > stale_after_seconds
        color = STATUS_STALE if self.is_stale else STATUS_OK
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")

    def animate(self) -> None:
        """Called on a fast (~30fps) timer by MainWindow so the graph keeps
        scrolling smoothly in real time between actual UDP readings,
        instead of only redrawing once per reading or per tick()."""
        self._graph.update()
