import warnings

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

    async def display_cell(self, *, height=None, width=None):
        from trame_client.ui.core import AbstractLayout

        if not hasattr(self, "ui") or not isinstance(self.ui, AbstractLayout):
            _error_msg = (
                f"The 'ui' attribute of {type(self).__name__} must be an instance of "
                "trame_client.ui.core.AbstractLayout to be compatible with Jupyter cell display."
            )
            raise TypeError(_error_msg)

        if not hasattr(self.ui, "display_cell"):
            await self._async_display()
            return

        await self.ui.display_cell(height=height, width=width)

    async def _async_display(self):
        from IPython.display import clear_output

        _warn_msg = (
            f"{type(self).__name__}._async_display() is deprecated and will be removed in a future version. "
            "To remove this warning, please upgrade your trame_client package version."
        )
        warnings.warn(
            _warn_msg,
            DeprecationWarning,
            stacklevel=2,
        )

        await self.ui.ready
        clear_output(wait=True)
        self.ui._ipython_display_()

    def _repr_html_(self):
        create_task(self.display_cell())
        return "<i>Launching trame server in the background...</i>"
