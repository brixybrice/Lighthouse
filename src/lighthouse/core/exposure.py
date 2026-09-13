"""Pure Lux -> EV -> f-stop exposure math. No Qt, no I/O — see CLAUDE.md for
where the formula comes from and what each constant means.
"""

import math
from dataclasses import dataclass

ISO_BASE = 100.0

# OD/0.3 stops, standard photographic ND naming.
ND_STOPS: dict[str, float] = {
    "None": 0.0,
    "ND0.3": 1.0,
    "ND0.6": 2.0,
    "ND0.9": 3.0,
    "ND1.2": 4.0,
    "ND1.5": 5.0,
    "ND1.8": 6.0,
    "ND2.1": 7.0,
    "ND2.4": 8.0,
    "ND2.7": 9.0,
}

# Standard 1/3-stop ISO/EI scale (matches real camera/meter dials): each
# full stop (100, 200, 400, 800, ...) followed by two third-stop values.
ISO_VALUES: list[float] = [
    25, 32, 40,
    50, 64, 80,
    100, 125, 160,
    200, 250, 320,
    400, 500, 640,
    800, 1000, 1250,
    1600, 2000, 2500,
    3200, 4000, 5000,
    6400, 8000, 10000,
    12800, 16000, 20000,
    25600,
]

# Common cine framerates and shutter angles — shutter speed is derived from
# the pair of these rather than picked directly (angle/360 of one frame).
FRAMERATES: list[float] = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]
SHUTTER_ANGLES: list[float] = [45, 90, 172.8, 180, 270, 360]

# Standard 1/3-stop aperture scale (matches real lens engravings): full
# stops (1.0, 1.4, 2.0, 2.8, 4.0, ...) each followed by two third-stop
# values (e.g. 2.0 -> 2.2 -> 2.5 -> 2.8). Extended slightly below 1.0 for
# the very fast apertures this app's low-light test scenarios can compute.
STANDARD_FSTOPS: list[float] = [
    0.7, 0.8, 0.9,
    1.0, 1.1, 1.2, 1.4, 1.6, 1.8,
    2.0, 2.2, 2.5, 2.8, 3.2, 3.5,
    4.0, 4.5, 5.0, 5.6, 6.3, 7.1,
    8.0, 9.0, 10, 11, 13, 14,
    16, 18, 20, 22, 25, 28,
    32, 36, 40, 45,
]


def snap_to_standard_fstop(fstop: float) -> float:
    """Nearest value on the standard 1/3-stop scale. Compared in log2 space
    since aperture stops are a geometric, not linear, progression."""
    if fstop <= 0:
        return STANDARD_FSTOPS[0]
    target = math.log2(fstop)
    return min(STANDARD_FSTOPS, key=lambda candidate: abs(math.log2(candidate) - target))


def lux_to_ev(lux: float, calibration_k: float) -> float | None:
    """EV at ISO 100 for a given lux reading. None if lux isn't positive
    (log2 undefined at/below zero — a dark or silent sensor)."""
    if lux <= 0 or calibration_k <= 0:
        return None
    return math.log2(lux) - math.log2(calibration_k)


def apply_iso(ev: float, iso: float, iso_base: float = ISO_BASE) -> float:
    return ev + math.log2(iso / iso_base)


def apply_nd(ev: float, nd_stops: float) -> float:
    return ev - nd_stops


def fstop_from_ev(ev: float, shutter_seconds: float) -> float:
    return math.sqrt((2**ev) * shutter_seconds)


@dataclass
class ExposureResult:
    ev_base: float
    ev_iso: float
    ev_effective: float
    fstop: float


def compute_exposure(
    lux: float,
    calibration_k: float,
    iso: float,
    nd_stops: float,
    shutter_seconds: float,
) -> ExposureResult | None:
    """Full Lux -> f-stop pipeline. None if lux is non-positive (nothing to
    compute an EV from)."""
    ev_base = lux_to_ev(lux, calibration_k)
    if ev_base is None:
        return None
    ev_iso = apply_iso(ev_base, iso)
    ev_effective = apply_nd(ev_iso, nd_stops)
    fstop = fstop_from_ev(ev_effective, shutter_seconds)
    return ExposureResult(ev_base=ev_base, ev_iso=ev_iso, ev_effective=ev_effective, fstop=fstop)


def format_fstop_number(fstop: float) -> str:
    """Plain numeric f-stop text, no 'f/' prefix — for compact displays
    like the tray, which snaps to snap_to_standard_fstop() first."""
    return f"{fstop:.2g}" if fstop < 10 else f"{fstop:.0f}"


def format_fstop(fstop: float) -> str:
    return f"f/{format_fstop_number(fstop)}"


def average_lux(values: list[float]) -> float | None:
    """Mean of the given lux readings, or None if there aren't any (e.g.
    every sensor is currently stale/offline)."""
    if not values:
        return None
    return sum(values) / len(values)


def shutter_seconds_from_angle(shutter_angle_degrees: float, framerate_fps: float) -> float | None:
    """One frame at `framerate_fps` exposed over `shutter_angle_degrees` out
    of a 360-degree rotating-shutter cycle — the standard cine way to think
    about exposure time. E.g. 172.8 degrees at 24fps = 1/50s."""
    if shutter_angle_degrees <= 0 or framerate_fps <= 0:
        return None
    return (shutter_angle_degrees / 360.0) / framerate_fps
