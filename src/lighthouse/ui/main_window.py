"""Main window: a Settings square on the left, sensor squares on the right
(or a single Average square, when that mode is on).

The UDP listener runs on its own QThread (workers/udp_listener_worker.py);
incoming readings and control changes both funnel into _recompute_all(),
the only place exposure math touches the UI. A fast (~30fps) timer repaints
the graphs so they scroll smoothly in real time, independent of the ~2Hz
UDP rate (see graph_widget.py) — same idea as Semaphore's animated curve.
A menu bar (tray) icon mirrors the live f-stops, and closing the window
just hides it — Quit lives in the tray menu, same pattern as any macOS
menu bar utility.
"""

import logging
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from lighthouse.core.exposure import (
    FRAMERATES,
    ISO_VALUES,
    ND_STOPS,
    SHUTTER_ANGLES,
    ExposureResult,
    average_lux,
    compute_exposure,
    shutter_seconds_from_angle,
)
from lighthouse.core.settings import AppSettings, load_app_settings, save_app_settings
from lighthouse.ui.average_panel import AveragePanel
from lighthouse.ui.sensor_panel import SensorPanel
from lighthouse.ui.settings_dialog import SettingsDialog
from lighthouse.ui.settings_panel import SettingsPanel
from lighthouse.ui.tray_icon import SensorTrayIcons
from lighthouse.workers.udp_listener_worker import UdpListenerWorker

_logger = logging.getLogger(__name__)

STATUS_REFRESH_MS = 500
ANIMATION_INTERVAL_MS = 33  # ~30fps, matches Semaphore's animated curve rate
# Worker stop should complete well within one select() timeout cycle
# (SELECT_TIMEOUT_SECONDS in the worker); this is a generous upper bound so
# closeEvent/_restart_worker never hang indefinitely on a stuck thread.
WORKER_STOP_TIMEOUT_MS = 2000


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lighthouse")

        self._settings: AppSettings = load_app_settings()
        self._panels: dict[str, SensorPanel] = {}
        self._quitting = False

        central = QWidget()
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)
        central.setLayout(root_layout)
        self.setCentralWidget(central)

        root_layout.addWidget(self._build_settings_panel())

        self._panels_layout = QHBoxLayout()
        self._panels_layout.setSpacing(8)
        root_layout.addLayout(self._panels_layout)
        root_layout.addStretch(1)

        self._average_panel = AveragePanel()
        self._rebuild_sensor_panels()

        self._worker: UdpListenerWorker | None = None
        self._start_worker()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_statuses)
        self._status_timer.start(STATUS_REFRESH_MS)

        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate)
        self._animation_timer.start(ANIMATION_INTERVAL_MS)

        self._tray = SensorTrayIcons()
        self._tray.connect_show_window(self._toggle_window_visibility)
        self._tray.connect_quit(self._quit_app)

        self._apply_floating_window()
        self._recompute_all()
        self._fit_to_content()

    def _fit_to_content(self) -> None:
        """Size the window to exactly fit its fixed-size square panels,
        instead of an arbitrary guessed height with empty space below."""
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16_777_215, 16_777_215)  # Qt's QWIDGETSIZE_MAX, undoes any prior clamp
        self.centralWidget().adjustSize()
        self.adjustSize()

    # -- UI construction ---------------------------------------------------

    def _build_settings_panel(self) -> SettingsPanel:
        panel = SettingsPanel()
        self._settings_panel = panel

        panel.iso_combo.addItems([_format_number(iso) for iso in ISO_VALUES])
        panel.iso_combo.setCurrentText(_format_number(self._settings.last_iso))
        panel.iso_combo.currentTextChanged.connect(self._on_controls_changed)

        panel.nd_combo.addItems(list(ND_STOPS.keys()))
        if self._settings.last_nd_label in ND_STOPS:
            panel.nd_combo.setCurrentText(self._settings.last_nd_label)
        panel.nd_combo.currentTextChanged.connect(self._on_controls_changed)

        panel.framerate_combo.addItems([_format_number(fps) for fps in FRAMERATES])
        panel.framerate_combo.setCurrentText(_format_number(self._settings.last_framerate))
        panel.framerate_combo.currentTextChanged.connect(self._on_controls_changed)

        panel.shutter_angle_combo.addItems([_format_number(angle) for angle in SHUTTER_ANGLES])
        panel.shutter_angle_combo.setCurrentText(_format_number(self._settings.last_shutter_angle))
        panel.shutter_angle_combo.currentTextChanged.connect(self._on_controls_changed)

        panel.sensors_button.clicked.connect(self._open_settings_dialog)

        panel.average_checkbox.setChecked(self._settings.show_average)
        panel.average_checkbox.toggled.connect(self._on_average_toggled)

        return panel

    def _rebuild_sensor_panels(self) -> None:
        for panel in self._panels.values():
            panel.setParent(None)
            panel.deleteLater()
        self._panels = {}

        for sensor_id, cfg in self._settings.sensors.items():
            panel = SensorPanel(sensor_id, cfg.label, cfg.ip, cfg.port)
            self._panels[sensor_id] = panel

        self._average_panel.set_sensor_histories({p.sensor_id: p.history for p in self._panels.values()})
        self._rebuild_display()

    def _rebuild_display(self) -> None:
        """Swaps what's shown in panels_layout between the individual
        sensor squares and the single Average square — the underlying
        SensorPanel objects (and their histories) keep running either way,
        only their visual placement changes."""
        while self._panels_layout.count():
            item = self._panels_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if self._settings.show_average:
            self._panels_layout.addWidget(self._average_panel)
        else:
            for panel in self._panels.values():
                self._panels_layout.addWidget(panel)

        self._fit_to_content()

    # -- Worker lifecycle ----------------------------------------------------

    def _start_worker(self) -> None:
        sensor_ports = {sensor_id: cfg.port for sensor_id, cfg in self._settings.sensors.items()}
        self._worker = UdpListenerWorker(sensor_ports)
        self._worker.reading_received.connect(self._on_reading)
        self._worker.listener_error.connect(self._on_listener_error)
        self._worker.start()

    def _stop_worker(self) -> None:
        if self._worker is None:
            return
        self._worker.request_stop()
        self._worker.wait(WORKER_STOP_TIMEOUT_MS)
        self._worker = None

    def _restart_worker(self) -> None:
        self._stop_worker()
        self._start_worker()

    # -- Settings dialog / floating window / average toggle -----------------

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self._settings.sensors, self._settings.floating_window, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return

        self._settings.sensors = dialog.result_sensors()
        self._settings.floating_window = dialog.result_floating()
        save_app_settings(self._settings)

        self._rebuild_sensor_panels()
        self._restart_worker()
        self._apply_floating_window()
        self._recompute_all()

    def _on_average_toggled(self, checked: bool) -> None:
        self._settings.show_average = checked
        save_app_settings(self._settings)
        self._rebuild_display()
        self._recompute_all()

    def _apply_floating_window(self) -> None:
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._settings.floating_window)
        if was_visible:
            self.show()

    # -- Exposure computation ------------------------------------------------

    def _on_controls_changed(self) -> None:
        self._settings.last_iso = self._current_iso() or self._settings.last_iso
        self._settings.last_nd_label = self._settings_panel.nd_combo.currentText()
        self._settings.last_framerate = self._current_framerate() or self._settings.last_framerate
        self._settings.last_shutter_angle = self._current_shutter_angle() or self._settings.last_shutter_angle
        save_app_settings(self._settings)
        self._recompute_all()

    def _current_iso(self) -> float | None:
        try:
            iso = float(self._settings_panel.iso_combo.currentText().strip())
        except ValueError:
            return None
        return iso if iso > 0 else None

    def _current_framerate(self) -> float | None:
        try:
            fps = float(self._settings_panel.framerate_combo.currentText().strip())
        except ValueError:
            return None
        return fps if fps > 0 else None

    def _current_shutter_angle(self) -> float | None:
        try:
            angle = float(self._settings_panel.shutter_angle_combo.currentText().strip())
        except ValueError:
            return None
        return angle if angle > 0 else None

    def _current_shutter_seconds(self) -> float | None:
        framerate = self._current_framerate()
        angle = self._current_shutter_angle()
        if framerate is None or angle is None:
            return None
        return shutter_seconds_from_angle(angle, framerate)

    def _on_reading(self, sensor_id: str, lux: float) -> None:
        panel = self._panels.get(sensor_id)
        if panel is None:
            return
        panel.set_reading(lux, time.monotonic())
        self._recompute_all()

    def _on_listener_error(self, message: str) -> None:
        _logger.error("UDP listener error: %s", message)
        self.statusBar().showMessage(message, 10_000)

    def _exposure_for(self, lux: float | None, calibration_k: float) -> ExposureResult | None:
        if lux is None:
            return None
        iso = self._current_iso()
        shutter_seconds = self._current_shutter_seconds()
        if iso is None or shutter_seconds is None:
            return None
        nd_stops = ND_STOPS.get(self._settings_panel.nd_combo.currentText(), 0.0)
        return compute_exposure(lux, calibration_k, iso, nd_stops, shutter_seconds)

    def _recompute_panel(self, sensor_id: str) -> None:
        panel = self._panels[sensor_id]
        calibration_k = self._settings.sensors[sensor_id].calibration_k
        panel.set_exposure(self._exposure_for(panel.last_lux, calibration_k))

    def _recompute_average(self, now: float) -> None:
        fresh_lux = [p.last_lux for p in self._panels.values() if p.last_lux is not None and not p.is_stale]
        avg_lux = average_lux(fresh_lux)
        self._average_panel.update_average(avg_lux, now)
        # Averages the raw lux curves (what's actually plotted), then runs
        # that single averaged value through the normal pipeline once —
        # simplest match for "one averaged value", not a log2/EV-space
        # average. Calibration K is normally the same across sensors; if
        # it isn't, this uses their mean K as an approximation rather than
        # picking one sensor's K arbitrarily.
        sensor_ks = [self._settings.sensors[p.sensor_id].calibration_k for p in self._panels.values()]
        calibration_k = average_lux(sensor_ks) or 1.0
        self._average_panel.set_exposure(self._exposure_for(avg_lux, calibration_k))

    def _recompute_all(self) -> None:
        now = time.monotonic()
        for sensor_id in self._panels:
            self._recompute_panel(sensor_id)
        self._recompute_average(now)
        self._update_tray()

    def _refresh_statuses(self) -> None:
        now = time.monotonic()
        for panel in self._panels.values():
            panel.tick(now, self._settings.stale_after_seconds)
        self._average_panel.tick(now)
        self._recompute_average(now)
        self._update_tray()

    def _animate(self) -> None:
        for panel in self._panels.values():
            panel.animate()
        self._average_panel.animate()

    def _update_tray(self) -> None:
        if self._settings.show_average:
            entries = {self._average_panel.label: (self._average_panel.last_fstop_value, self._average_panel.is_stale)}
        else:
            entries = {panel.label: (panel.last_fstop_value, panel.is_stale) for panel in self._panels.values()}
        self._tray.update_display(entries)

    # -- Window / tray lifecycle ---------------------------------------------

    def _toggle_window_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "_tray"):
            self._tray.set_toggle_text(showing=True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if hasattr(self, "_tray"):
            self._tray.set_toggle_text(showing=False)

    def _quit_app(self) -> None:
        self._quitting = True
        self.close()

    def closeEvent(self, event) -> None:
        if not self._quitting:
            event.ignore()
            self.hide()
            return
        self._stop_worker()
        save_app_settings(self._settings)
        self._tray.hide_all()
        super().closeEvent(event)
        QApplication.instance().quit()


def _format_number(value: float) -> str:
    return f"{value:g}"
