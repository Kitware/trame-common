import asyncio

import pytest

from trame_common.exec.throttle import Throttle


def test_throttle_coalesces_calls_and_uses_latest_args():
    calls = []

    async def run():
        t = Throttle(lambda *a: calls.append(a), ts=0.01)
        t(1)
        t(2)
        t(3)
        await t._pending_task
        assert calls == [(3,)]
        assert t._pending is False

    asyncio.run(run())


def test_throttle_calls_again_after_delay():
    calls = []

    async def run():
        t = Throttle(lambda *a: calls.append(a), ts=0.01)
        t("first")
        await t._pending_task

        t("second")
        await t._pending_task

        assert calls == [("first",), ("second",)]

    asyncio.run(run())


def test_throttle_resets_pending_state_after_exception():
    calls = []

    class TestError(ValueError): ...

    def fn(value):
        calls.append(value)
        if value == "boom":
            raise TestError()

    async def run():
        t = Throttle(fn, ts=0.01)

        t("boom")
        with pytest.raises(TestError):
            await t._pending_task

        # A previous bug left `_pending` stuck at True after an exception,
        # which silently dropped every subsequent call forever.
        assert t._pending is False

        t("ok")
        await t._pending_task
        assert calls == ["boom", "ok"]

        # Check if not awaiting task is fine
        t("boom")
        await asyncio.sleep(0.02)
        assert t._pending is False
        t("ok")
        await t._pending_task
        assert calls == ["boom", "ok", "boom", "ok"]

    asyncio.run(run())
