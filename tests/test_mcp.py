import asyncio
from types import SimpleNamespace

import pytest

from trame_common.decorators import mcp
from trame_common.obj import mcp as mcp_options
from trame_common.obj.component import TrameComponent
from trame_common.obj.mcp import Progress
from trame_common.utils.ids import _to_id, next_id

# -----------------------------------------------------------------------------
# A stub server: TrameComponent only reaches the MCP through server.mcp
# -----------------------------------------------------------------------------


class StubMCP:
    def __init__(self):
        self.calls = []

    def expose_object(self, obj, name, description=None, read_only=False):
        self.calls.append(("expose", obj, name, description, read_only))

    def _remove_object(self, obj):
        self.calls.append(("remove", obj))

    def _add_component_tools(self, obj):
        self.calls.append(("add tools", obj))

    def _remove_component_tools(self, obj):
        self.calls.append(("remove tools", obj))


class StubServer:
    def __init__(self):
        self.state = SimpleNamespace(translator=None)
        self.mcp = StubMCP()


class ServerWithoutMCP:
    def __init__(self):
        self.state = SimpleNamespace(translator=None)


# -----------------------------------------------------------------------------
# Ids
# -----------------------------------------------------------------------------


def test_id_format():
    assert _to_id(1) == "0x1"
    assert _to_id(10) == "0xa"
    assert _to_id(255) == "0xff"
    assert _to_id(4096) == "0x1000"


def test_ids_are_unique_and_never_start_with_a_letter():
    ids = [next_id() for _ in range(5000)]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("0x") and i == i.lower() for i in ids)


# -----------------------------------------------------------------------------
# Markers
# -----------------------------------------------------------------------------


def test_permission_names():
    assert mcp_options.permission_names(None) == ()
    assert mcp_options.permission_names("files") == ("files",)
    assert mcp_options.permission_names(["files", "scripts"]) == ("files", "scripts")
    with pytest.raises(TypeError):
        mcp_options.permission_names(3)
    with pytest.raises(TypeError):
        mcp_options.permission_names(["files", ""])


def test_mcp_method():
    @mcp.method
    def bare(self): ...

    @mcp.method(name="go", read_only=True, concurrent=True, requires="files")
    async def with_options(self): ...

    assert bare._trame_mcp_method == {
        "name": None,
        "description": None,
        "read_only": False,
        "annotations": None,
        "concurrent": False,
        "requires": (),
    }
    assert with_options._trame_mcp_method["name"] == "go"
    assert with_options._trame_mcp_method["requires"] == ("files",)
    assert with_options._trame_mcp_method["concurrent"] is True
    assert asyncio.iscoroutinefunction(with_options)
    with pytest.raises(TypeError):
        mcp.method(requires=5)
    with pytest.raises(TypeError, match="annotations"):
        mcp.method(annotations=["destructiveHint"])
    with pytest.raises(TypeError, match="annotations"):

        class Bad(TrameComponent, mcp={"methods": {"go": {"annotations": True}}}):
            def go(self): ...


def test_mcp_property():
    class Thing:
        def __init__(self):
            self._path = "a"

        @mcp.property
        def plain(self) -> int:
            """A plain one."""
            return 1

        @mcp.property(requires="files", description="The path")
        def path(self) -> str:
            return self._path

        @path.setter(requires="scripts")
        def path(self, value):
            self._path = value

    thing = Thing()
    assert isinstance(Thing.plain, property)
    assert isinstance(Thing.path, mcp.property)
    assert thing.plain == 1
    assert Thing.plain.__doc__ == "A plain one."
    assert Thing.plain._trame_mcp_property == {
        "description": None,
        "requires": (),
        "set_requires": (),
    }

    thing.path = "b"
    assert thing.path == "b"
    assert Thing.path._trame_mcp_property["requires"] == ("files",)
    assert Thing.path._trame_mcp_property["set_requires"] == ("scripts",)
    assert Thing.path._trame_mcp_property["description"] == "The path"


# -----------------------------------------------------------------------------
# Class options
# -----------------------------------------------------------------------------


def test_keyword_validation():
    with pytest.raises(ValueError, match="unknown options"):

        class Bad(TrameComponent, mcp={"fields": ["a"]}):
            pass

    with pytest.raises(ValueError, match="is not a method"):

        class Typo(TrameComponent, mcp={"methods": ["nope"]}):
            pass

    with pytest.raises(ValueError, match="has no property"):

        class TypoProperty(TrameComponent, mcp={"properties": ["nope"]}):
            pass

    with pytest.raises(TypeError):

        class NotADict(TrameComponent, mcp="yes"):
            pass


def test_class_options_layers():
    class Base(TrameComponent, mcp={"description": "Base", "methods": ["reset"]}):
        def reset(self): ...

        def other(self): ...

        @property
        def size(self):
            return 1

    class Sub(Base, mcp={"methods": {"other": "Another one"}}):
        pass

    options = Sub.mcp_describe()
    assert options["declared"] is True
    assert options["description"] is None  # never inherited
    assert options["methods"] == {"reset": {}, "other": {"description": "Another one"}}

    # mcp_describe applies on top of the keyword, and to subclasses
    Base.mcp_describe(methods={"reset": False}, properties=["size"])
    options = Sub.mcp_describe()
    assert options["methods"] == {
        "reset": False,
        "other": {"description": "Another one"},
    }
    assert options["properties"] == {"size": {}}
    assert Base.mcp_describe()["description"] == "Base"

    with pytest.raises(ValueError, match="already set"):
        Base.mcp_describe(description="again")

    # A subclass keyword still applies under a base's mcp_describe
    class Leaf(Sub, mcp={"methods": ["reset"]}):
        pass

    assert Leaf.mcp_describe()["methods"]["reset"] == {}


def test_hidden_and_declared():
    class Marked(TrameComponent):
        @mcp.method
        def go(self): ...

    class Hidden(Marked, mcp=False):
        pass

    class Visible(Hidden, mcp={"description": "Back"}):
        pass

    class Plain(TrameComponent):
        def go(self): ...

    class Empty(TrameComponent, mcp=True):
        pass

    assert mcp_options.declares(Marked)
    assert not mcp_options.declares(Hidden)
    assert mcp_options.declares(Visible)
    assert not mcp_options.declares(Plain)
    assert mcp_options.declares(Empty)
    assert Marked.mcp_describe()["declared"] is None
    assert Hidden.mcp_describe()["declared"] is False

    Plain.mcp_describe(False)
    assert not mcp_options.declares(Plain)


def test_describe_arguments():
    class Thing(TrameComponent):
        def go(self): ...

    with pytest.raises(TypeError):
        Thing.mcp_describe(True, description="no")
    Thing.mcp_describe(True)
    assert mcp_options.declares(Thing)


def test_defining_or_describing_a_class_changes_the_version():
    before = mcp_options.options_version()

    class Told(TrameComponent):
        pass

    after = mcp_options.options_version()
    assert after > before
    Told.mcp_describe(True)
    assert mcp_options.options_version() > after


def test_registry_keeps_definition_order():
    class First(TrameComponent):
        pass

    class Second(TrameComponent):
        pass

    classes = mcp_options.declared_classes()
    assert classes.index(First) < classes.index(Second)


# -----------------------------------------------------------------------------
# TrameComponent and the server's MCP
# -----------------------------------------------------------------------------


class Viewer(TrameComponent):
    @mcp.method
    def reset_camera(self): ...


class NotForAgents(TrameComponent):
    def reset_camera(self): ...


def test_not_exposed_when_built():
    server = StubServer()
    Viewer(server)
    NotForAgents(server)
    assert server.mcp.calls == []


def test_expose_and_unexpose():
    server = StubServer()
    viewer = Viewer(server)
    assert viewer.mcp is server.mcp

    viewer.mcp_expose("left", description="The left view.", read_only=True)
    assert server.mcp.calls[-1] == ("expose", viewer, "left", "The left view.", True)

    viewer._unbind_annotated_methods()
    assert server.mcp.calls[-1] == ("remove", viewer)


def test_server_without_mcp():
    viewer = Viewer(ServerWithoutMCP())
    viewer._unbind_annotated_methods()


def test_progress_reports_nothing_by_itself():
    progress = Progress()
    assert progress  # truthy, so `if progress:` only skips the app's own calls
    assert asyncio.run(progress(1, total=2, message="Half")) is None


def test_app_mcp_enabled(monkeypatch):
    from trame_common.obj import app

    monkeypatch.setattr(app, "get_server", lambda server, **_: server)

    server = StubServer()
    app.TrameApp(server, mcp_enabled=True)
    assert server.mcp.enabled is True

    # Left out, it doesn't touch the MCP server
    app.TrameApp(ServerWithoutMCP())


def test_component_ids():
    server = StubServer()
    a, b = Viewer(server), NotForAgents(server)
    assert a._id != b._id
    assert a._id == a._id
    assert not a._id[0].isalpha()


def test_exposable_mixes_into_any_class():
    class Base:
        def __init__(self, value):
            self.value = value

    class Camera(Base, mcp_options.MCPExposable, mcp={"description": "A camera"}):
        @mcp.property
        def zoom(self) -> float:
            return 1.0

    camera = Camera(3)
    assert camera.value == 3  # its own __init__ runs untouched
    assert camera._id == camera._id
    assert mcp_options.declares(Camera)
    assert Camera.mcp_describe()["description"] == "A camera"
    with pytest.raises(RuntimeError, match="no trame server"):
        camera.mcp_expose("camera")

    camera.server = StubServer()
    camera.mcp_expose("camera")
    assert camera.server.mcp.calls[-1] == ("expose", camera, "camera", None, False)


# -----------------------------------------------------------------------------
# First-class tools and constructors
# -----------------------------------------------------------------------------


def test_first_class_markers():
    @mcp.tool(name="snap", read_only=True, requires="files")
    def tool(self): ...

    @mcp.resource("app://guide", mime_type="text/markdown")
    def resource(self): ...

    @mcp.prompt
    def prompt(self): ...

    assert tool._trame_mcp_tool == {
        "name": "snap",
        "description": None,
        "read_only": True,
        "annotations": None,
        "concurrent": False,
        "requires": ("files",),
    }
    assert resource._trame_mcp_resource["uri"] == "app://guide"
    assert prompt._trame_mcp_prompt == {"name": None, "description": None}


class Console(TrameComponent):
    @mcp.tool
    def status(self): ...


def test_first_class_markers_are_bound_not_objects():
    server = StubServer()
    console = Console(server)
    assert not mcp_options.declares(Console)  # not an object
    assert server.mcp.calls == [("add tools", console)]
    console._unbind_annotated_methods()
    assert server.mcp.calls[-1] == ("remove tools", console)
    assert mcp_options.first_class_members(Console) == [
        ("status", "_trame_mcp_tool", Console.status._trame_mcp_tool)
    ]


class Panel(TrameComponent):
    @mcp.tool
    def zoom(self): ...

    @mcp.prompt
    def guide(self): ...

    @mcp.tool
    def after(self): ...


class SubPanel(Panel):
    @mcp.tool
    def added(self): ...

    def zoom(self): ...  # no longer a tool


def test_first_class_members_in_definition_order():
    def names(cls):
        return [name for name, _, _ in mcp_options.first_class_members(cls)]

    assert names(Panel) == ["zoom", "guide", "after"]
    assert names(SubPanel) == ["guide", "after", "added"]


def test_true_and_dicts():
    assert mcp_options.normalize_options(True) == {}
    assert mcp_options.normalize_options({"methods": ["go"]}) == {"methods": {"go": {}}}
    with pytest.raises(ValueError, match="unknown options"):
        mcp_options.normalize_options({"all_fields": True})


def test_module_holds_only_the_decorators():
    public = sorted(name for name in vars(mcp) if not name.startswith("_"))
    assert public == ["constructor", "method", "prompt", "property", "resource", "tool"]
    assert issubclass(mcp.property, property)


# -----------------------------------------------------------------------------
# Constructors
# -----------------------------------------------------------------------------


def test_constructor_marker():
    class Viewer(TrameComponent):
        @mcp.constructor(description="A new viewer", requires="views")
        @classmethod
        def new(cls, server, title: str):
            viewer = cls(server)
            viewer.title = title
            return viewer

    assert mcp_options.declares(Viewer)  # the marker declares the class
    assert mcp_options.class_options(Viewer)["constructor"] == {
        "name": "new",
        "description": "A new viewer",
        "requires": ("views",),
    }
    constructor = Viewer._mcp_constructor()
    assert constructor == mcp_options.Constructor(
        attr="new", description="A new viewer", requires=("views",)
    )

    class SubViewer(Viewer):  # inherited
        pass

    assert SubViewer._mcp_constructor().attr == "new"

    class Closed(Viewer, mcp={"constructor": False}):
        pass

    assert Closed._mcp_constructor() is None


def test_constructor_marker_goes_on_a_classmethod():
    with pytest.raises(TypeError, match="not a staticmethod"):
        mcp.constructor(staticmethod(lambda: None))

    with pytest.raises(TypeError, match="marks a classmethod"):

        class Plain(TrameComponent):
            @mcp.constructor
            def new(self, server): ...

    with pytest.raises(ValueError, match="several constructors"):

        class Twice(TrameComponent):
            @mcp.constructor
            @classmethod
            def first(cls, server): ...

            @classmethod
            @mcp.constructor
            def second(cls, server): ...


def test_constructor_option():
    class Panel(TrameComponent, mcp={"constructor": "default"}):
        pass

    assert Panel._mcp_constructor() == mcp_options.Constructor(attr=None)

    class Named(TrameComponent, mcp={"constructor": {"name": "make"}}):
        @classmethod
        def make(cls, server):
            return cls(server)

    assert Named._mcp_constructor().attr == "make"

    with pytest.raises(ValueError, match="not a classmethod"):

        class Typo(TrameComponent, mcp={"constructor": "nope"}):
            pass

    with pytest.raises(ValueError, match="unknown options"):

        class Unknown(TrameComponent, mcp={"constructor": {"name": "x", "y": 1}}):
            pass

    with pytest.raises(TypeError, match="constructor must be"):

        class Wrong(TrameComponent, mcp={"constructor": 3}):
            pass

    # mcp_describe() goes over the keyword
    class Described(TrameComponent, mcp={"constructor": "default"}):
        pass

    Described.mcp_describe(constructor=False)
    assert Described._mcp_constructor() is None


def test_default_constructor_checks_init():
    class Simple(TrameComponent, mcp={"constructor": "default"}):
        pass

    assert mcp_options.default_constructor_problem(Simple) is None

    class NeedsMore(TrameComponent, mcp={"constructor": "default"}):
        def __init__(self, server, size):
            super().__init__(server)
            self.size = size

    constructor = NeedsMore._mcp_constructor()
    assert "size" in constructor.problem
    assert "@mcp.constructor" in constructor.problem

    class NoServer(mcp_options.MCPExposable, mcp={"constructor": "default"}):
        pass

    assert "NoServer(server)" in NoServer._mcp_constructor().problem
