import inspect
import logging

from trame_common.obj import mcp as mcp_options
from trame_common.obj.mcp import MCPExposable

__all__ = [
    "TrameComponent",
]

logger = logging.getLogger(__name__)


def can_be_decorated(x):
    return inspect.ismethod(x) or inspect.isfunction(x)


class TrameComponent(MCPExposable):
    """
    Base trame class that has access to a trame server instance
    on which we provide simple accessor and method decoration capabilities.

    A subclass declares what agents may use with the ``@mcp.method`` and
    ``@mcp.property`` markers (``from trame.decorators import mcp``), or with
    the ``mcp=`` class keyword, which takes True (declared, with no other
    options), False (never exposed) or a dict of ``description``,
    ``all_methods``, ``methods``, ``properties`` and ``constructor``. Agents
    reach an instance once the app names it (``mcp_expose``), or through a
    visible property of an object they reach.

    A component built once may also mark the app's own tools, resources and
    prompts (``@mcp.tool``, ``@mcp.resource``, ``@mcp.prompt``): they are
    added when it is built and removed when it is unbound.
    """

    # The callbacks it binds on the server keep it alive while in use
    _mcp_hold_weakly = True

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

    # -------------------------------------------------------------------------
    # Agents (MCP)
    # -------------------------------------------------------------------------

    @property
    def mcp(self):
        """Return the MCP server of the associated trame server"""
        return self.server.mcp

    def _mcp_declares(self):
        return mcp_options.declares(type(self))

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
                    self.ctrl.trigger(f"{trigger_name}")(fn)

            # Handle @ctrl.[add, once, add_task, set]
            if "_trame_controller" in fn.__dict__:
                actions = fn.__dict__["_trame_controller"]
                for action in actions:
                    name = action.get("name")
                    method = action.get("method")
                    decorate = getattr(self.ctrl, method)
                    logger.debug("ctrl.%s(%s)(%s)", method, name, k[0])
                    decorate(name)(fn)

        # Agents (MCP): add the app's own tools it marks (a component built once)
        if mcp_options.first_class_members(type(self)) and hasattr(self.server, "mcp"):
            self.server.mcp._add_component_tools(self)

    def _unbind_annotated_methods(self):
        methods_state = set()
        ctrl_fn = {}  # {name: [fn...]}
        # Look for method decorator
        for k in inspect.getmembers(self.__class__, can_be_decorated):
            fn = getattr(self, k[0])

            # Handle @state.change
            if "_trame_state_change" in fn.__dict__:
                methods_state.add(fn)

            # Handle @trigger
            if "_trame_trigger_names" in fn.__dict__:
                self.ctrl.trigger_unregister(fn)

            # Handle @ctrl
            if "_trame_controller" in fn.__dict__:
                actions = fn.__dict__["_trame_controller"]
                for action in actions:
                    name = action.get("name")
                    ctrl_fn.setdefault(name, set()).add(fn)

        # Remove trigger methods
        for method_name in getattr(self.__class__, "_trame_trigger_method_names", []):
            self.ctrl.trigger_unregister(getattr(self, method_name, None))

        # Remove @state.change
        if methods_state:
            for k, v in self.state._change_callbacks.items():
                self.state._change_callbacks[k] = [
                    (fn, translator) for fn, translator in v if fn not in methods_state
                ]

        # Remove ctrl method:
        if ctrl_fn:
            for k, v in ctrl_fn.items():
                ctrl_fn = self.ctrl[k]
                for f in v:
                    ctrl_fn.discard(f)

        # Withdraw its names from agents (MCP), and the tools it added
        if self._mcp_declares() and hasattr(self.server, "mcp"):
            self.mcp_unexpose()
        if mcp_options.first_class_members(type(self)) and hasattr(self.server, "mcp"):
            self.server.mcp._remove_component_tools(self)
