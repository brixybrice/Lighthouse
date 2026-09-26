"""QThread that owns the UDP listening sockets for every configured sensor,
for its whole lifetime.

One thread, one select() loop over N raw UDP sockets (not one thread per
sensor) — see CLAUDE.md "Matériel et protocole": each sensor is just a bare
ASCII float per packet, no OSC/framing to decode, so there's no need for a
per-sensor blocking server. Requests from the UI thread (stop) only ever
set a threading.Event — never touch a Qt object from here; the loop reports
back only via Signals carrying plain values.
"""

import logging
import select
import socket
import threading

from PySide6.QtCore import QThread, Signal

_logger = logging.getLogger(__name__)

# How long select() blocks with nothing to do — bounds how quickly
# request_stop() takes effect, not the sensor's own ~2Hz send rate.
SELECT_TIMEOUT_SECONDS = 0.5


class UdpListenerWorker(QThread):
    reading_received = Signal(str, float)  # sensor_id, lux
    listener_error = Signal(str)

    def __init__(self, sensor_ports: dict[str, int], parent=None):
        super().__init__(parent)
        self._sensor_ports = dict(sensor_ports)
        self._stop = threading.Event()

    def request_stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _make_socket(port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        reuseport = getattr(socket, "SO_REUSEPORT", None)
        if reuseport is not None:
            # Lets this coexist with TouchDesigner if it's also listening.
            sock.setsockopt(socket.SOL_SOCKET, reuseport, 1)
        sock.bind(("0.0.0.0", port))
        sock.setblocking(False)
        return sock

    @staticmethod
    def _trigger_local_network_prompt() -> None:
        # macOS only shows the "Local Network" permission prompt when an app
        # sends to the LAN; a receive-only app never triggers it and gets
        # broadcast packets silently dropped. One harmless byte to the
        # discard port is enough.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(b"\0", ("255.255.255.255", 9))
        except OSError as exc:
            _logger.info("Local-network trigger send failed (harmless): %s", exc)

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:  # never a silent thread crash
            _logger.error("Unexpected error in UDP listener", exc_info=True)
            self.listener_error.emit(f"Unexpected error: {exc}")

    def _run(self) -> None:
        sockets: dict[socket.socket, str] = {}
        for sensor_id, port in self._sensor_ports.items():
            try:
                sockets[self._make_socket(port)] = sensor_id
            except OSError as exc:
                _logger.error("Could not listen on port %d for %s: %s", port, sensor_id, exc)
                self.listener_error.emit(f"{sensor_id}: could not listen on port {port} ({exc})")

        if not sockets:
            _logger.error("No UDP port could be opened, listener thread exiting")
            return

        _logger.info("Listening for %s on ports %s", list(sockets.values()), [s.getsockname()[1] for s in sockets])
        self._trigger_local_network_prompt()
        try:
            while not self._stop.is_set():
                ready, _, _ = select.select(list(sockets.keys()), [], [], SELECT_TIMEOUT_SECONDS)
                for sock in ready:
                    try:
                        data, _addr = sock.recvfrom(65535)
                    except OSError as exc:
                        _logger.warning("recvfrom failed: %s", exc)
                        continue
                    sensor_id = sockets[sock]
                    try:
                        lux = float(data.decode("ascii").strip())
                    except (UnicodeDecodeError, ValueError):
                        _logger.warning("Unparsable packet from %s: %r", sensor_id, data)
                        continue
                    self.reading_received.emit(sensor_id, lux)
        finally:
            for sock in sockets:
                sock.close()
            _logger.info("UDP listener stopped")
