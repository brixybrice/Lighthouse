"""The exposure-controls panel: same fixed square as SensorPanel so it
lines up with the sensor row, label+dropdown on one line per parameter to
fit four controls plus a header in that limited height. Purely structural —
MainWindow owns all the wiring (combo signals, the settings-dialog button)."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from lighthouse.ui.sensor_panel import SQUARE_SIZE
from lighthouse.ui.theme import BORDER
from lighthouse.ui.widgets import WideComboBox

LABEL_WIDTH = 40


class SettingsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SQUARE_SIZE, SQUARE_SIZE)
        self.setObjectName("SensorPanel")  # same border styling as SensorPanel
        self.setStyleSheet(
            f"QFrame#SensorPanel {{ border: 1px solid {BORDER}; border-radius: 6px; padding: 6px; }}"
        )

        name_label = QLabel("Settings")
        name_label.setStyleSheet("font-weight: bold;")

        self.sensors_button = QPushButton("⚙")
        self.sensors_button.setToolTip("Edit sensor IPs/ports, add or remove sensors")
        self.sensors_button.setFixedSize(40, 40)
        self.sensors_button.setFlat(True)
        gear_font = QFont()
        gear_font.setPointSize(22)
        self.sensors_button.setFont(gear_font)

        top_row = QHBoxLayout()
        top_row.addWidget(name_label)
        top_row.addStretch(1)
        top_row.addWidget(self.sensors_button)

        self.iso_combo = WideComboBox()
        self.iso_combo.setEditable(True)

        self.nd_combo = WideComboBox()

        self.framerate_combo = WideComboBox()
        self.framerate_combo.setEditable(True)

        self.shutter_angle_combo = WideComboBox()
        self.shutter_angle_combo.setEditable(True)

        self.average_checkbox = QCheckBox("Average")
        self.average_checkbox.setToolTip("Combine all sensors into one averaged reading")

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.addLayout(top_row)
        layout.addLayout(_row("ISO", self.iso_combo))
        layout.addLayout(_row("ND", self.nd_combo))
        layout.addLayout(_row("FPS", self.framerate_combo))
        layout.addLayout(_row("Angle", self.shutter_angle_combo))
        layout.addWidget(self.average_checkbox)
        layout.addStretch(1)
        self.setLayout(layout)


def _row(label_text: str, widget: QComboBox) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(6)
    label = QLabel(label_text)
    label.setFixedWidth(LABEL_WIDTH)
    layout.addWidget(label)
    layout.addWidget(widget, stretch=1)
    return layout
