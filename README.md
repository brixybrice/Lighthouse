# Lighthouse

Standalone macOS lux meter and exposure calculator, driven by two
ESP32/BH1750 sensors on the network. Suggests an f-stop from the measured
lux, the chosen ISO/EI, ND filter, framerate, and shutter angle.

See [`CLAUDE.md`](CLAUDE.md) (in French) for the full project context,
hardware/protocol notes, and target architecture.

## Features

- Live per-sensor square panel, sized to fit the window exactly (no wasted
  space): current lux, computed EV and f-stop, a smoothly-animated
  (~30fps, like Semaphore's spectrum curve) 30-second graduated lux graph
  pinned to the bottom edge, and a bigger status dot to the left of the
  sensor name (green = live, red = stale, no extra text).
- **Average mode** (checkbox in the Settings panel): combines every
  sensor into one square panel showing each sensor's raw curve plus the
  averaged curve overlaid, and a single averaged lux/EV/f-stop — the
  per-sensor panels keep updating in the background so switching back is
  instant.
- A matching square Settings panel (same size as the sensor panels):
  ISO/EI (standard 1/3-stop scale, 25–25600), ND filter (None to ND2.7),
  framerate, and shutter angle, each label on the same line as its
  dropdown. Applies to every sensor at once and persists across restarts.
  Defaults: EI 800, 24fps, 172.8° shutter angle (=1/50s).
- Sensor settings dialog (gear icon in the Settings panel): edit each
  sensor's label/IP/port/calibration constant, add or remove sensors, and
  toggle "keep window floating" (always-on-top).
- macOS menu bar: one native status item per sensor (real AppKit text, not
  a scaled icon — or a single "Average" item in Average mode) showing its
  live f-stop, snapped to the standard 1/3-stop aperture scale (e.g.
  `f/2.8`); greyed out rather than removed if that sensor's connection
  drops. Closing the window just hides it, `Quit` lives in the tray menu.

## Hardware

- Two ESP32 boards, each with a BH1750 lux sensor, on fixed IPs by default
  (more can be added from the settings dialog):
  - Sensor 1: `192.168.5.51`, sending plain-text UDP on port `2121`
  - Sensor 2: `192.168.5.52`, sending plain-text UDP on port `8000`
- Each packet is a bare ASCII float already in lux (e.g. `b'11.67'`), at
  roughly 2 messages/second per sensor — see `CLAUDE.md` for how this was
  confirmed.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running

```bash
source .venv/bin/activate
lighthouse
```

(or `python -m lighthouse.main`)

## Probing the sensors directly

No project dependencies needed — useful to sanity-check the hardware on
its own:

```bash
python scripts/probe_udp_sensors.py
```

## Testing

```bash
source .venv/bin/activate
pytest
```

## Architecture

```
src/lighthouse/
├── main.py                     # QApplication bootstrap
├── core/                        # no Qt imports — unit-testable headless
│   ├── exposure.py              # pure EV/ISO/ND/f-stop functions
│   ├── history.py                # rolling time-windowed sample history (feeds the graph)
│   ├── settings.py              # typed dataclass (sensors dict, last ISO/ND/shutter, floating_window)
│   ├── _storage.py               # atomic JSON persistence
│   └── logging_setup.py          # rotating log file under Application Support
├── workers/
│   └── udp_listener_worker.py    # single QThread, select() over one raw UDP socket per sensor
└── ui/
    ├── theme.py                  # dark theme
    ├── widgets.py                 # WideComboBox (fixes Qt's too-narrow popup)
    ├── graph_widget.py            # multi-curve, real-time-scrolling strip-chart (QPainter)
    ├── sensor_panel.py            # one square panel per sensor (QFrame, not QGroupBox)
    ├── average_panel.py            # square panel combining all sensors into one curve/value
    ├── settings_panel.py           # matching square panel: ISO/ND/framerate/angle + gear icon + Average toggle
    ├── settings_dialog.py         # sensor add/edit/remove + floating-window toggle
    ├── tray_icon.py                # native NSStatusItem text per sensor (PyObjC)
    └── main_window.py             # settings panel (left) + sensor panels or average panel (right)
```

## Acknowledgments

Originally a module inside a larger TouchDesigner project. The exposure
formula (Lux → EV → f-stop) is ported from that project's Python DAT
script; the real UDP protocol was re-validated from scratch against the
live hardware (`scripts/probe_udp_sensors.py`) since the original
`.toe` file is password-encrypted and no longer inspectable.
