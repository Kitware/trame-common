import sys
import time
from contextlib import contextmanager

__all__ = [
    "LOGGER",
    "Logger",
    "Timer",
    "enable",
    "timer",
]


class Logger:
    __slots__ = ("abort", "enabled", "log_perf", "log_perf_fps")

    def __init__(self):
        self.abort = False
        self.enabled = False
        self.log_perf = None
        self.log_perf_fps = None
        self.use_print()

    def action(self, msg):
        self.log_perf(time.perf_counter(), msg, 0)

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
        elif LOGGER.enabled:
            self.log(self.t0, self.msg, self.dt)


LOGGER = Logger()


def enable(value: bool = True) -> Logger:
    """Turn performance instrumentation on or off globally."""
    LOGGER.enabled = bool(value)
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
