from trame.app import get_server

from trame_common.exec.asynchronous import create_task
from trame_common.obj.component import TrameComponent


class TrameApp(TrameComponent):
    """
    Base trame class that has access to a trame server instance
    on which we provide simple accessor and method decoration capabilities.
    """

    def __init__(self, server=None, client_type="vue3", ctx_name=None, **_):
        super().__init__(get_server(server, client_type=client_type), ctx_name=ctx_name)

    async def _async_display(self):
        await self.ui.ready
        self.ui._ipython_display_()

    def _ipython_display_(self):
        create_task(self._async_display())
