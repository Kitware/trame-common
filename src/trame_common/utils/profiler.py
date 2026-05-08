import sys
import time
from contextlib import contextmanager

__all__ = [
    "LOGGER",
    "Logger",
    "Timer",
    "clear_filter",
    "enable",
    "exclude",
    "include",
    "timer",
]

KEY_SIZE = 2


class Filter:
    def __init__(self):
        self._include = {}
        self._exclude = {}

    def include(self, head):
        if len(head) < KEY_SIZE:
            return

        key = head[:KEY_SIZE]
        self._include.setdefault(key, set()).add(head)

    def exclude(self, head):
        if len(head) < KEY_SIZE:
            return

        key = head[:KEY_SIZE]
        self._exclude.setdefault(key, set()).add(head)

    def clear(self, include=True, exclude=True):
        if include:
            self._include.clear()
        if exclude:
            self._exclude.clear()

    def keep(self, msg):
        if not self._exclude or not self._include or len(msg) < KEY_SIZE:
            return True

        # compute key for fast lookup
        key = msg[:KEY_SIZE]

        # Exclude
        if self._exclude:
            exclude_set = self._exclude.get(key, [])
            for head in exclude_set:
                if msg.startswith(head):
                    return False

        # Include all if empty
        if not self._include:
            return True

        # Only show includes
        if self._include:
            include_set = self._include.get(key, [])
            for head in include_set:
                if msg.startswith(head):
                    return True

        return False


class Logger:
    __slots__ = ("abort", "enabled", "filter", "log_perf", "log_perf_fps")

    def __init__(self):
        self.filter = Filter()
        self.abort = False
        self.enabled = False
        self.log_perf = None
        self.log_perf_fps = None
        self.use_print()

    def action(self, msg, duration=0):
        if self.enabled and self.filter.keep(msg):
            self.log_perf(time.perf_counter(), msg, duration)

    def use_print(self, file=sys.stderr):
        def log_perf(ts, msg, dt_ms):
            print(f"{msg:<60} {ts:10.3f} {dt_ms:8.2f} ms", file=file, flush=True)

        def log_perf_fps(ts, msg, dt_ms):
            print(
                f"{msg:<60} {ts:10.3f} {dt_ms:8.2f} ms {1000 / dt_ms:8.1f} fps",
                file=file,
                flush=True,
            )

        self.log_perf = log_perf
        self.log_perf_fps = log_perf_fps
        return self

    def use_loguru(self):
        from loguru import logger

        logger.add(
            sys.stdout,
            format="[PERF] {message}",
            level="TRACE",
            filter="trame_lumo_view.perf",
        )

        def log_perf(ts, msg, dt_ms):
            logger.trace("{:<60} {:10.3f} {:8.2f} ms", msg, ts, dt_ms)

        def log_perf_fps(ts, msg, dt_ms):
            logger.trace(
                "{:<60} {:8.3f} {:10.2f} ms {:8.1f} fps", msg, ts, dt_ms, 1000 / dt_ms
            )

        self.log_perf = log_perf
        self.log_perf_fps = log_perf_fps
        return self


class Timer:
    __slots__ = ("abort", "dt", "log", "msg", "t0")

    def __init__(self, msg: str, show_fps: bool = False):
        self.msg = msg
        self.abort = False
        self.t0 = 0
        self.dt = 0
        self.log = LOGGER.log_perf_fps if show_fps else LOGGER.log_perf

    def __enter__(self):
        self.on_start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.on_end()

    def on_start(self, *_, **__):
        self.t0 = time.perf_counter()

    def on_end(self, *_, **__):
        self.dt = (time.perf_counter() - self.t0) * 1000.0
        if self.abort:
            self.abort = False
        elif LOGGER.enabled and LOGGER.filter.keep(self.msg):
            self.log(self.t0, self.msg, self.dt)


LOGGER = Logger()


def enable(value: bool = True) -> Logger:
    """Turn performance instrumentation on or off globally."""
    LOGGER.enabled = bool(value)
    return LOGGER


def include(value: str = "") -> Logger:
    """Register filter to only include messages starting with value."""
    LOGGER.filter.include(value)
    return LOGGER


def exclude(value: str = "") -> Logger:
    """Register filter to exclude messages starting with value."""
    LOGGER.filter.exclude(value)
    return LOGGER


def clear_filter(include: bool = True, exclude: bool = True) -> Logger:
    """Clear filter."""
    LOGGER.filter.clear(include, exclude)
    return LOGGER


@contextmanager
def timer(label: str, show_fps: bool = False):
    # Skip
    if not LOGGER.enabled:
        yield LOGGER
        return

    # Time it
    t0 = time.perf_counter()
    try:
        yield LOGGER
    finally:
        if LOGGER.abort:
            LOGGER.abort = False
        else:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            if show_fps:
                LOGGER.log_perf_fps(t0, label, dt_ms)
            else:
                LOGGER.log_perf(t0, label, dt_ms)
