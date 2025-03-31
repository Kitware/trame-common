import inspect
import logging

__all__ = [
    "TrameComponent",
]

logger = logging.getLogger(__name__)


def can_be_decorated(x):
    return inspect.ismethod(x) or inspect.isfunction(x)


class TrameComponent:
    """
    Base trame class that has access to a trame server instance
    on which we provide simple accessor and method decoration capabilities.
    """

    def __init__(self, server, ctx_name=None, **_):
        """
        Initialize TrameComponent with its server.

        Keyword arguments:
        server -- the server to link to (default None)
        ctx_name -- name to use to bind current instance to server.context (default None)
        """
        self._server = server

        if ctx_name:
            self.ctx[ctx_name] = self

        self._bind_annotated_methods()

    @property
    def server(self):
        """Return the associated trame server instance"""
        return self._server

    @property
    def state(self):
        """Return the associated server state"""
        return self.server.state

    @property
    def ctrl(self):
        """Return the associated server controller"""
        return self.server.controller

    @property
    def ctx(self):
        """Return the associated server context"""
        return self.server.context

    def _bind_annotated_methods(self):
        # Look for method decorator
        for k in inspect.getmembers(self.__class__, can_be_decorated):
            fn = getattr(self, k[0])

            # Handle @state.change
            s_translator = self.state.translator
            if "_trame_state_change" in fn.__dict__:
                state_change_names = fn.__dict__["_trame_state_change"]
                logger.debug(
                    "state.change(%s)(%s)",
                    [f"{s_translator.translate_key(v)}" for v in state_change_names],
                    k[0],
                )
                self.state.change(*[f"{v}" for v in state_change_names])(fn)

            # Handle @trigger
            if "_trame_trigger_names" in fn.__dict__:
                trigger_names = fn.__dict__["_trame_trigger_names"]
                for trigger_name in trigger_names:
                    logger.debug("trigger(%s)(%s)", trigger_name, k[0])
                    self.server.trigger(f"{trigger_name}")(fn)

            # Handle @ctrl.[add, once, add_task, set]
            if "_trame_controller" in fn.__dict__:
                actions = fn.__dict__["_trame_controller"]
                for action in actions:
                    name = action.get("name")
                    method = action.get("method")
                    decorate = getattr(self.ctrl, method)
                    logger.debug("ctrl.%s(%s)(%s)", method, name, k[0])
                    decorate(name)(fn)

    def _unbind_annotated_methods(self):
        # Look for method decorator
        for k in inspect.getmembers(self.__class__, can_be_decorated):
            fn = getattr(self, k[0])

            # Handle @state.change
            methods_to_detach = {}
            if "_trame_state_change" in fn.__dict__:
                methods_to_detach.add(fn)

            if methods_to_detach:
                for fn_list in self.state._change_callbacks.values():
                    to_remove = set(fn_list) | methods_to_detach
                    for fn in to_remove:
                        fn_list.remove(fn)

            # Handle @trigger
            # TODO

            # Handle @ctrl
            # TODO
