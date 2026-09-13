"""Sensor setup dialog: edit/add/remove sensors (label, IP, port, calibration),
plus the "keep window floating" toggle. All validation happens here — the
caller (MainWindow) only ever gets back a fully valid sensors dict."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lighthouse.core.settings import SensorConfig, next_sensor_id

COLUMNS = ["Label", "IP address", "Port", "Calibration K"]


class SettingsDialog(QDialog):
    def __init__(self, sensors: dict[str, SensorConfig], floating_window: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sensor Settings")
        self.setMinimumWidth(420)

        self._row_sensor_ids: list[str] = []
        self._result_sensors: dict[str, SensorConfig] | None = None
        self._result_floating = floating_window

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        for sensor_id, cfg in sensors.items():
            self._add_row(sensor_id, cfg)

        add_button = QPushButton("Add sensor")
        add_button.clicked.connect(self._on_add_sensor)
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._on_remove_selected)

        table_buttons = QHBoxLayout()
        table_buttons.addWidget(add_button)
        table_buttons.addWidget(remove_button)
        table_buttons.addStretch(1)

        self._floating_checkbox = QCheckBox("Keep window floating (always on top)")
        self._floating_checkbox.setChecked(floating_window)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self._table)
        layout.addLayout(table_buttons)
        layout.addWidget(self._floating_checkbox)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def _add_row(self, sensor_id: str, cfg: SensorConfig) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._row_sensor_ids.append(sensor_id)
        self._table.setItem(row, 0, QTableWidgetItem(cfg.label))
        self._table.setItem(row, 1, QTableWidgetItem(cfg.ip))
        self._table.setItem(row, 2, QTableWidgetItem(str(cfg.port)))
        self._table.setItem(row, 3, QTableWidgetItem(str(cfg.calibration_k)))

    def _on_add_sensor(self) -> None:
        existing = {sensor_id: None for sensor_id in self._row_sensor_ids}
        new_id = next_sensor_id(existing)
        index = len(self._row_sensor_ids) + 1
        self._add_row(new_id, SensorConfig(label=f"Sensor {index}", ip="0.0.0.0", port=0, calibration_k=2.5))

    def _on_remove_selected(self) -> None:
        rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)
            del self._row_sensor_ids[row]

    def _on_accept(self) -> None:
        sensors: dict[str, SensorConfig] = {}
        for row, sensor_id in enumerate(self._row_sensor_ids):
            label = self._table.item(row, 0).text().strip()
            ip = self._table.item(row, 1).text().strip()
            port_text = self._table.item(row, 2).text().strip()
            calibration_text = self._table.item(row, 3).text().strip()

            if not label or not ip:
                self._reject_row(row, "Label and IP address can't be empty.")
                return
            try:
                port = int(port_text)
                if not (0 < port <= 65535):
                    raise ValueError
            except ValueError:
                self._reject_row(row, "Port must be a number between 1 and 65535.")
                return
            try:
                calibration_k = float(calibration_text)
                if calibration_k <= 0:
                    raise ValueError
            except ValueError:
                self._reject_row(row, "Calibration K must be a positive number.")
                return

            sensors[sensor_id] = SensorConfig(label=label, ip=ip, port=port, calibration_k=calibration_k)

        if not sensors:
            QMessageBox.warning(self, "Sensor Settings", "At least one sensor is required.")
            return

        self._result_sensors = sensors
        self._result_floating = self._floating_checkbox.isChecked()
        self.accept()

    def _reject_row(self, row: int, message: str) -> None:
        self._table.selectRow(row)
        QMessageBox.warning(self, "Sensor Settings", message)

    def result_sensors(self) -> dict[str, SensorConfig]:
        return self._result_sensors

    def result_floating(self) -> bool:
        return self._result_floating
