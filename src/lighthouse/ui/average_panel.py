"""The combined "average of sensors" view: same square as SensorPanel, but
the graph overlays every sensor's raw curve (dim) plus the average (bold),
and the lux/EV/f-stop readout shows only the average — never per-sensor
values, per how this mode was asked for.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from lighthouse.core.exposure import ExposureResult, format_fstop
from lighthouse.core.history import SampleHistory
from lighthouse.ui.graph_widget import GraphSeries, LuxGraphWidget
from lighthouse.ui.sensor_panel import GRAPH_HEIGHT, GRAPH_WINDOW_SECONDS, SQUARE_SIZE
from lighthouse.ui.theme import BORDER, STATUS_OK, STATUS_STALE, TEXT_DIM

DIM_SERIES_COLOR = BORDER


class AveragePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = "Average"
        self.last_lux: float | None = None
        self.last_fstop_text = "f/—"
        self.last_fstop_value: float | None = None
        self.is_stale = True
        self._history = SampleHistory(window_seconds=GRAPH_WINDOW_SECONDS)

        self.setFixedSize(SQUARE_SIZE, SQUARE_SIZE)
        self.setObjectName("SensorPanel")
        self.setStyleSheet(
            f"QFrame#SensorPanel {{ border: 1px solid {BORDER}; border-radius: 6px; padding: 6px; }}"
        )

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 16px;")

        self._name_label = QLabel(self.label)
        self._name_label.setStyleSheet("font-weight: bold;")

        self._info_label = QLabel("no sensors")
        self._info_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")

        self._lux_label = QLabel("— lux")
        self._lux_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self._ev_label = QLabel("EV —")
        self._ev_label.setStyleSheet(f"color: {TEXT_DIM};")

        self._fstop_label = QLabel("f/—")
        self._fstop_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        self._fstop_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._graph = LuxGraphWidget(self._history)
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
        layout.setSpacing(6)
        layout.addLayout(name_row)
        layout.addWidget(self._info_label)
        layout.addLayout(readout_row)
        layout.addStretch(1)
        layout.addWidget(self._graph)
        self.setLayout(layout)

    def set_sensor_histories(self, histories: dict[str, SampleHistory]) -> None:
        self._info_label.setText(f"average of {len(histories)} sensor(s)" if histories else "no sensors")
        series = [GraphSeries(history, DIM_SERIES_COLOR, 1) for history in histories.values()]
        series.append(GraphSeries(self._history, STATUS_OK, 2))
        self._graph.set_series(series)

    def update_average(self, lux: float | None, timestamp: float) -> None:
        self.last_lux = lux
        if lux is None:
            self._lux_label.setText("— lux")
            return
        self._lux_label.setText(f"{lux:.2f} lux")
        self._history.add(timestamp, lux)

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

    def tick(self, now: float) -> None:
        self._history.trim(now)
        self.is_stale = self.last_lux is None
        color = STATUS_STALE if self.is_stale else STATUS_OK
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")

    def animate(self) -> None:
        self._graph.update()
