"""Time-windowed sample history — pure data structure, no Qt.

Feeds the rolling lux graph: keeps only samples within the last
`window_seconds`. Trimming happens both when a new sample arrives and via
an explicit `trim(now)` call, so the window also shrinks with no new data
(e.g. a sensor gone offline empties out visually instead of freezing).
"""

from dataclasses import dataclass, field


@dataclass
class SampleHistory:
    window_seconds: float = 30.0
    _samples: list[tuple[float, float]] = field(default_factory=list)

    def add(self, timestamp: float, value: float) -> None:
        self._samples.append((timestamp, value))
        self.trim(timestamp)

    def trim(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.pop(0)

    @property
    def samples(self) -> list[tuple[float, float]]:
        return list(self._samples)

    def bounds(self) -> tuple[float, float] | None:
        if not self._samples:
            return None
        values = [v for _, v in self._samples]
        return min(values), max(values)

    def __len__(self) -> int:
        return len(self._samples)
