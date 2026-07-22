"""
Wain Network Monitor
====================

Lightweight per-adapter network throughput sampling for the dashboard's
Network card (v2.22.0). Built for watching big project syncs / VPN
transfers (e.g. robocopy to a render node) without leaving Wain.

https://github.com/sbuff25/RenderManager

Uses psutil (optional dependency - the UI degrades gracefully to an
install hint when missing). Rates are computed from counter deltas
between samples, so call sample() at a steady interval (the UI uses 1s).

Adapter selection is automatic: the busiest adapter of the last sample
wins, with hysteresis so the display doesn't flap between adapters.
cycle() lets the user click through adapters manually; auto-selection
resumes only when the monitor is re-created.
"""

import time
from collections import deque

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

# Adapters that are never interesting to watch
_IGNORE_PREFIXES = ("Loopback", "lo", "vEthernet (WSL")

HISTORY_LEN = 90  # seconds of sparkline at 1s sampling


class NetMonitor:
    """Samples per-NIC counters and tracks one 'active' adapter."""

    def __init__(self):
        self.available = PSUTIL_AVAILABLE
        self.selected: str = ""          # adapter currently displayed
        self.manual: bool = False        # user cycled manually - stop auto-switching
        self.up_bps: float = 0.0
        self.down_bps: float = 0.0
        self.session_sent: int = 0       # bytes since monitor start (selected adapter)
        self.session_recv: int = 0
        self.up_history = deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN)
        self._last: dict = {}            # nic -> (sent, recv)
        self._t_last: float = 0.0
        self._base: dict = {}            # nic -> (sent, recv) at start, for session totals
        self._adapters: list = []
        if self.available:
            self._prime()

    def _counters(self) -> dict:
        out = {}
        try:
            for nic, c in psutil.net_io_counters(pernic=True).items():
                if any(nic.startswith(p) for p in _IGNORE_PREFIXES):
                    continue
                out[nic] = (c.bytes_sent, c.bytes_recv)
        except Exception:
            pass
        return out

    def _prime(self):
        self._last = self._counters()
        self._base = dict(self._last)
        self._t_last = time.monotonic()
        self._adapters = list(self._last.keys())

    def cycle(self):
        """Manually step to the next adapter (click-to-cycle in the UI)."""
        if not self._adapters:
            return
        self.manual = True
        try:
            i = self._adapters.index(self.selected)
        except ValueError:
            i = -1
        self.selected = self._adapters[(i + 1) % len(self._adapters)]
        self.up_history.clear()
        self.up_history.extend([0.0] * HISTORY_LEN)

    def sample(self):
        """Take a sample; updates rates/history for the selected adapter."""
        if not self.available:
            return
        now = time.monotonic()
        dt = max(now - self._t_last, 0.25)
        cur = self._counters()
        self._adapters = list(cur.keys())

        # per-adapter deltas
        rates = {}
        for nic, (s, r) in cur.items():
            ls, lr = self._last.get(nic, (s, r))
            rates[nic] = ((s - ls) / dt, (r - lr) / dt)

        # auto-select: busiest adapter, with 2x hysteresis so we don't flap
        if not self.manual and rates:
            busiest = max(rates, key=lambda n: sum(rates[n]))
            if self.selected not in rates:
                self.selected = busiest
            elif sum(rates[busiest]) > 2.0 * sum(rates.get(self.selected, (0, 0))):
                self.selected = busiest

        if self.selected in rates:
            self.up_bps, self.down_bps = rates[self.selected]
            s, r = cur[self.selected]
            bs, br = self._base.get(self.selected, (s, r))
            self.session_sent = s - bs
            self.session_recv = r - br
        else:
            self.up_bps = self.down_bps = 0.0
        self.up_history.append(self.up_bps)

        self._last = cur
        self._t_last = now


def fmt_rate(bps: float) -> str:
    """Human rate: chooses KB/s / MB/s with sane precision."""
    mbs = bps / (1024 * 1024)
    if mbs >= 100:
        return f"{mbs:,.0f} MB/s"
    if mbs >= 1:
        return f"{mbs:.1f} MB/s"
    kbs = bps / 1024
    if kbs >= 1:
        return f"{kbs:.0f} KB/s"
    return "0 KB/s"


def fmt_bytes(n: int) -> str:
    gb = n / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = n / (1024 ** 2)
    if mb >= 1:
        return f"{mb:.0f} MB"
    return f"{n // 1024} KB"
