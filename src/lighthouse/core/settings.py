"""Persisted application settings: per-sensor network/calibration config,
the last ISO/ND/shutter chosen by the user, and window behavior."""

from dataclasses import dataclass, field

from lighthouse.core._storage import APP_SUPPORT_DIR, read_json, write_json_atomic

SETTINGS_FILE = APP_SUPPORT_DIR / "settings.json"


@dataclass
class SensorConfig:
    label: str
    ip: str
    port: int
    calibration_k: float = 2.5

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "ip": self.ip,
            "port": self.port,
            "calibration_k": self.calibration_k,
        }

    @classmethod
    def from_dict(cls, data: dict, defaults: "SensorConfig") -> "SensorConfig":
        return cls(
            label=data.get("label", defaults.label),
            ip=data.get("ip", defaults.ip),
            port=data.get("port", defaults.port),
            calibration_k=data.get("calibration_k", defaults.calibration_k),
        )


def _default_sensors() -> dict[str, SensorConfig]:
    # IPs/ports confirmed live on the studio network — see CLAUDE.md.
    return {
        "sensor1": SensorConfig(label="Sensor 1", ip="192.168.5.51", port=2121),
        "sensor2": SensorConfig(label="Sensor 2", ip="192.168.5.52", port=8000),
    }


def next_sensor_id(sensors: dict[str, SensorConfig]) -> str:
    """A fresh, never-colliding key for a sensor added via the settings dialog."""
    index = len(sensors) + 1
    while f"sensor{index}" in sensors:
        index += 1
    return f"sensor{index}"


@dataclass
class AppSettings:
    sensors: dict[str, SensorConfig] = field(default_factory=_default_sensors)
    last_iso: float = 800.0
    last_nd_label: str = "None"
    # 172.8 degrees at 24fps = 1/50s — a common cine default.
    last_framerate: float = 24.0
    last_shutter_angle: float = 172.8
    stale_after_seconds: float = 4.0
    floating_window: bool = False
    show_average: bool = False

    def to_dict(self) -> dict:
        return {
            "sensors": {sensor_id: cfg.to_dict() for sensor_id, cfg in self.sensors.items()},
            "last_iso": self.last_iso,
            "last_nd_label": self.last_nd_label,
            "last_framerate": self.last_framerate,
            "last_shutter_angle": self.last_shutter_angle,
            "stale_after_seconds": self.stale_after_seconds,
            "floating_window": self.floating_window,
            "show_average": self.show_average,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        defaults = cls()
        raw_sensors = data.get("sensors") or {}
        if raw_sensors:
            # Not limited to the default two ids — sensors added via the
            # settings dialog must round-trip too.
            fallback = SensorConfig(label="Sensor", ip="0.0.0.0", port=0)
            sensors = {
                sensor_id: SensorConfig.from_dict(raw, defaults.sensors.get(sensor_id, fallback))
                for sensor_id, raw in raw_sensors.items()
            }
        else:
            sensors = defaults.sensors
        return cls(
            sensors=sensors,
            last_iso=data.get("last_iso", defaults.last_iso),
            last_nd_label=data.get("last_nd_label", defaults.last_nd_label),
            last_framerate=data.get("last_framerate", defaults.last_framerate),
            last_shutter_angle=data.get("last_shutter_angle", defaults.last_shutter_angle),
            stale_after_seconds=data.get("stale_after_seconds", defaults.stale_after_seconds),
            floating_window=data.get("floating_window", defaults.floating_window),
            show_average=data.get("show_average", defaults.show_average),
        )


def load_app_settings(path=SETTINGS_FILE) -> AppSettings:
    raw = read_json(path, default=None)
    if not isinstance(raw, dict):
        return AppSettings()
    return AppSettings.from_dict(raw)


def save_app_settings(settings: AppSettings, path=SETTINGS_FILE) -> None:
    write_json_atomic(path, settings.to_dict())
