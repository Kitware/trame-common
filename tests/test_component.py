import asyncio
from contextlib import suppress

import pytest
from trame.app import TrameComponent, get_server
from trame.decorators import change, controller, trigger
from trame.ui.html import DivLayout
from trame.widgets import html
from trame_server.controller import FunctionNotImplementedError

YIELD_TIME = 0.01


@pytest.mark.asyncio
async def test_state():
    calls = []
    server = get_server("test_state")
    state = server.state
    state.a = 1

    class Dummy(TrameComponent):
        def __init__(self, server, name):
            super().__init__(server)
            self._name = name

        @change("a")
        def _a_changed(self, a, **_):
            calls.append(f"{self._name} = {a}")

    first = Dummy(server, "first")
    task = server.start(exec_mode="task", port=0)
    await server.ready

    assert calls == ["first = 1"]
    with state:
        state.a = 2
    await asyncio.sleep(YIELD_TIME)
    assert calls == ["first = 1", "first = 2"]

    first._unbind_annotated_methods()
    with state:
        state.a = 3
    await asyncio.sleep(YIELD_TIME)
    assert calls == ["first = 1", "first = 2"]

    second = Dummy(server, "second")
    with state:
        state.a = 4
    await asyncio.sleep(YIELD_TIME)
    assert calls == ["first = 1", "first = 2", "second = 4"]

    second._unbind_annotated_methods()
    with state:
        state.a = 5
    await asyncio.sleep(YIELD_TIME)
    assert calls == ["first = 1", "first = 2", "second = 4"]

    assert state.a == 5
    await server.stop()
    await task


@pytest.mark.asyncio
async def test_triggers():
    calls = []
    server = get_server("test_triggers")
    ctrl = server.controller

    class DummyTemplate(TrameComponent):
        def __init__(self, server, name):
            super().__init__(server)
            self._name = name
            self._build_ui()

        def click(self):
            calls.append(f"{self._name} clicked template")

        def _build_ui(self):
            with DivLayout(self.server, template_name=self._name) as self.ui:
                html.Button(
                    f"{self.ctrl.trigger_name(self.click)}",
                    click=self.click,
                )

    class Dummy(TrameComponent):
        def __init__(self, server, name):
            super().__init__(server)
            self._name = name

        def click(self):
            calls.append(f"{self._name} clicked")

        @trigger("me")
        def named_trigger(self):
            calls.append(f"{self._name} named trigger")

    def detached_method(): ...

    assert len(ctrl._triggers) == 0
    first = Dummy(server, "first")
    assert len(ctrl._triggers) == 1

    with DivLayout(server):
        html.Button("Click Me", click=first.click)
        html.Button("Click Me", click=ctrl.on_click)

    assert len(ctrl._triggers) == 3

    task = server.start(exec_mode="task", port=0)
    await server.ready
    # >>>
    x = DummyTemplate(server, "x")
    assert len(ctrl._triggers) == 4
    y = DummyTemplate(server, "y")
    # assert len(ctrl._triggers) == 5

    # assert len(ctrl._triggers) == 5
    ctrl.trigger("detach")(detached_method)
    # assert len(ctrl._triggers) == 6
    ctrl.trigger_unregister(detached_method)
    # assert len(ctrl._triggers) == 5
    first._unbind_annotated_methods()
    # assert len(ctrl._triggers) == 3
    ctrl.trigger_unregister(ctrl.on_click)
    # assert len(ctrl._triggers) == 2
    x._unbind_annotated_methods()
    # assert len(ctrl._triggers) == 1
    y._unbind_annotated_methods()
    # assert len(ctrl._triggers) == 0
    # <<<
    await server.stop()
    await task


def test_ctrl():
    calls = []
    server = get_server("test_ctrl")
    ctrl = server.controller

    class Dummy(TrameComponent):
        def __init__(self, server, name):
            super().__init__(server)
            self._name = name

        @controller.add("me")
        def method_add(self):
            calls.append(f"{self._name} me")

        @controller.once("yo")
        def method_once(self):
            calls.append(f"{self._name} yo")

        @controller.set("hello")
        def method_set(self):
            calls.append(f"{self._name} hello")

    first = Dummy(server, "first")
    assert ctrl.me.exists()
    assert ctrl.hello.exists()
    assert not ctrl.empty.exists()

    ctrl.yo.enable_empty()

    ctrl.me()
    ctrl.hello()
    ctrl.me()
    ctrl.yo()
    ctrl.yo()

    print(calls)
    assert calls == ["first me", "first hello", "first me", "first yo"]

    first._unbind_annotated_methods()

    with suppress(FunctionNotImplementedError):
        ctrl.hello()

    with suppress(FunctionNotImplementedError):
        ctrl.me()

    assert calls == ["first me", "first hello", "first me", "first yo"]

    assert not ctrl.me.exists()
    assert not ctrl.hello.exists()
