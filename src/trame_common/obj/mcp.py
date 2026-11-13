"""
What classes declare for agents (MCP), stored as plain data.

A class declares what agents may use with the ``mcp=`` class keyword, with
``Cls.mcp_describe()`` when it comes from another library, and with the
decorators of ``trame_common.decorators.mcp`` (``@mcp.method``,
``@mcp.property``, ``@mcp.constructor``...), which only attach the markers
defined here. This module checks and stores these options, and the trame
server (``server.mcp``) turns them into what agents see.

A class's options combine with those of its base classes, from the base
down. On each class, the keyword applies first, then the
``mcp_describe()`` call. ``False`` hides a class, and its subclasses until
one of them declares options again. ``True`` declares a class with no
other options.

Classes whose instances agents reach inherit :class:`MCPExposable`, as
``TrameComponent`` and trame-dataclass's ``StateDataModel`` do. A package
that brings its own type of class overrides its ``_mcp_*`` hooks, and can
handle extra options of its own and pass these common ones here.

A long tool or method reports how far it has got through a parameter of type
:class:`Progress`.
"""

import inspect
import weakref
from dataclasses import dataclass

from trame_common.utils.ids import next_id

__all__ = [
    "CLASS_OPTIONS",
    "Constructor",
    "Field",
    "MCPExposable",
    "Progress",
    "changed",
    "class_options",
    "declared_classes",
    "declares",
    "default_constructor_problem",
    "describe_class",
    "first_class_members",
    "has_markers",
    "options_version",
    "permission_names",
    "register_class",
    "set_class_keyword",
]

KEYWORD_ATTR = "_trame_mcp_keyword"
DESCRIBED_ATTR = "_trame_mcp_described"

CLASS_OPTIONS = ("description", "all_methods", "methods", "properties", "constructor")
PROPERTY_OPTIONS = ("description", "read_only", "schema", "requires")
METHOD_OPTIONS = ("description", "read_only", "annotations", "concurrent", "requires")
CONSTRUCTOR_OPTIONS = ("name", "description", "requires")
DEFAULT_CONSTRUCTOR = "default"  # constructor="default": cls(server, **values)

# The attributes the decorators set on what they mark
METHOD_MARKER = "_trame_mcp_method"
PROPERTY_MARKER = "_trame_mcp_property"
CONSTRUCTOR_MARKER = "_trame_mcp_constructor"
TOOL_MARKER = "_trame_mcp_tool"
RESOURCE_MARKER = "_trame_mcp_resource"
PROMPT_MARKER = "_trame_mcp_prompt"

# What a component built once offers as the app's own tools
FIRST_CLASS_MARKERS = (TOOL_MARKER, RESOURCE_MARKER, PROMPT_MARKER)

_CLASSES = []  # weakref.ref to every declaring-capable class, in definition order
_version = 0  # bumped whenever what a class declares may have changed


def options_version():
    """A number that changes whenever a class is registered or described, so
    that what is derived from class options can be cached."""
    return _version


def changed():
    """Note that what a class declares may have changed (for packages that
    store options of their own)."""
    global _version  # noqa: PLW0603
    _version += 1


def permission_names(value, label="requires"):
    """
    Return a ``requires=`` value as a tuple of permission names.

    :param value: None, a permission name, or a list of them.
    :param label: the option name used in the error message.
    """
    if value is None:
        return ()
    names = (value,) if isinstance(value, str) else value
    try:
        names = tuple(names)
    except TypeError:
        names = None
    if names is None or not all(isinstance(n, str) and n for n in names):
        msg = f"{label} must be a permission name or a list of them, got {value!r}"
        raise TypeError(msg)
    return names


# -----------------------------------------------------------------------------
# Class registry
# -----------------------------------------------------------------------------


def register_class(cls):
    """Record a class that may declare something for agents, such as a
    ``TrameComponent`` subclass, in definition order."""
    _CLASSES.append(weakref.ref(cls))
    changed()


def declared_classes():
    """The registered classes that still exist, in definition order."""
    alive = [ref() for ref in _CLASSES]
    if len(alive) != len(_CLASSES) and None in alive:
        _CLASSES[:] = [
            ref for ref, cls in zip(_CLASSES, alive, strict=True) if cls is not None
        ]
    return [cls for cls in alive if cls is not None]


# -----------------------------------------------------------------------------
# Markers
# -----------------------------------------------------------------------------


def declares(cls):
    """Whether agents may reach instances of ``cls``: True when a keyword or
    ``mcp_describe()`` declares the class, or when it has markers, unless it
    is hidden."""
    declared = class_options(cls)["declared"]
    return has_markers(cls) if declared is None else declared


def _function(member):
    """The function behind a class member (a classmethod's too), or None."""
    if isinstance(member, classmethod):
        member = member.__func__
    return member if inspect.isfunction(member) else None


def has_markers(cls):
    """Whether ``cls`` or a base marks something agents reach through the
    object tools: a method with ``@mcp.method``, a property with
    ``@mcp.property`` or a constructor with ``@mcp.constructor``. The markers
    of first-class tools (``@mcp.tool``...) don't count."""
    for klass in cls.__mro__:
        for member in vars(klass).values():
            if isinstance(member, property) and hasattr(member, PROPERTY_MARKER):
                return True
            fn = _function(member)
            if fn is not None and (
                METHOD_MARKER in fn.__dict__ or CONSTRUCTOR_MARKER in fn.__dict__
            ):
                return True
    return False


def marked_constructors(klass):
    """``{attribute name: options}`` of the constructors that ``klass`` itself
    marks with ``@mcp.constructor``."""
    found = {}
    for name, member in vars(klass).items():
        fn = _function(member)
        if fn is not None and CONSTRUCTOR_MARKER in fn.__dict__:
            if not isinstance(member, classmethod):
                msg = f"{klass.__name__}.{name}: @mcp.constructor marks a classmethod"
                raise TypeError(msg)
            found[name] = fn.__dict__[CONSTRUCTOR_MARKER]
    return found


def check_markers(cls):
    """Reject markers in the wrong place: a class marks one constructor at
    most, and only on a classmethod."""
    constructors = marked_constructors(cls)
    if len(constructors) > 1:
        msg = f"{cls.__name__} marks several constructors: {sorted(constructors)}"
        raise ValueError(msg)


_FIRST_CLASS = weakref.WeakKeyDictionary()  # cls -> its first-class members


def first_class_members(cls):
    """``[(attribute name, marker, options)]`` for the methods of ``cls``
    marked with ``@mcp.tool``, ``@mcp.resource`` or ``@mcp.prompt``."""
    if cls in _FIRST_CLASS:
        return _FIRST_CLASS[cls]
    members = {}  # in definition order, bases first
    for klass in reversed(cls.__mro__):
        members.update(vars(klass))
    found = []
    for name, fn in members.items():
        if not inspect.isfunction(fn):
            continue
        for marker in FIRST_CLASS_MARKERS:
            if marker in fn.__dict__:
                found.append((name, marker, fn.__dict__[marker]))
    _FIRST_CLASS[cls] = found
    return found


# -----------------------------------------------------------------------------
# Options
# -----------------------------------------------------------------------------


def _members(entries, allowed, label):
    """``properties=`` / ``methods=`` as ``{name: options dict or False}``."""
    if entries is None:
        return {}
    if isinstance(entries, str):
        msg = f"{label} must be a list of names or a dict, got a string"
        raise TypeError(msg)
    if not isinstance(entries, dict):
        entries = dict.fromkeys(entries, True)
    result = {}
    for name, given in entries.items():
        if not isinstance(name, str) or not name:
            msg = f"{label}: names must be non-empty strings, got {name!r}"
            raise TypeError(msg)
        if given is False:
            result[name] = False
            continue
        if given is True or given is None:
            options = {}
        elif isinstance(given, str):
            options = {"description": given}
        elif isinstance(given, dict):
            options = dict(given)
        else:
            msg = (
                f"{label}[{name!r}] must be True, False, a description or a dict, "
                f"got {given!r}"
            )
            raise TypeError(msg)
        unknown = sorted(set(options) - set(allowed))
        if unknown:
            msg = (
                f"{label}[{name!r}]: unknown options {unknown}, "
                f"allowed: {list(allowed)}"
            )
            raise ValueError(msg)
        for key in ("read_only", "concurrent"):
            if key in options and not isinstance(options[key], bool):
                msg = f"{label}[{name!r}].{key} must be True or False"
                raise TypeError(msg)
        if "annotations" in options and not isinstance(options["annotations"], dict):
            msg = (
                f"{label}[{name!r}].annotations must be a dict of MCP tool annotations"
            )
            raise TypeError(msg)
        if "schema" in options and not isinstance(options["schema"], dict):
            msg = f"{label}[{name!r}].schema must be a dict of JSON Schema keywords"
            raise TypeError(msg)
        if "requires" in options:
            options["requires"] = permission_names(
                options["requires"], f"{label}[{name!r}].requires"
            )
        result[name] = options
    return result


def normalize_options(value, label="mcp"):
    """
    Validate one declaration (a class keyword or an ``mcp_describe()`` call).

    Returns None (declares nothing), False (hidden) or a dict with only the
    options given.
    """
    if value is None or value is False:
        return value
    if value is True:
        return {}
    allowed = CLASS_OPTIONS
    if not isinstance(value, dict):
        msg = f"{label} must be True, False or a dict of {list(allowed)}, got {value!r}"
        raise TypeError(msg)
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        msg = f"{label}: unknown options {unknown}, allowed: {list(allowed)}"
        raise ValueError(msg)

    result = {}
    if value.get("description") is not None:
        if not isinstance(value["description"], str):
            msg = f"{label}: description must be a string"
            raise TypeError(msg)
        result["description"] = value["description"]
    if value.get("all_methods") is not None:
        if not isinstance(value["all_methods"], bool):
            msg = f"{label}: all_methods must be True or False"
            raise TypeError(msg)
        result["all_methods"] = value["all_methods"]
    if value.get("properties") is not None:
        result["properties"] = _members(
            value["properties"], PROPERTY_OPTIONS, "properties"
        )
    if value.get("methods") is not None:
        result["methods"] = _members(value["methods"], METHOD_OPTIONS, "methods")
    if value.get("constructor") is not None:
        result["constructor"] = _constructor_option(value["constructor"], label)
    return result


def _constructor_option(value, label):
    """``constructor=`` as False or ``{"name", "description", "requires"}``;
    the name "default" stands for ``cls(server, **values)``."""
    if value is False:
        return False
    if isinstance(value, str):
        value = {"name": value}
    if not isinstance(value, dict):
        msg = (
            f"{label}: constructor must be a classmethod name, a dict of "
            f"{list(CONSTRUCTOR_OPTIONS)} or False, got {value!r}"
        )
        raise TypeError(msg)
    unknown = sorted(set(value) - set(CONSTRUCTOR_OPTIONS))
    if unknown:
        msg = (
            f"{label}: constructor: unknown options {unknown}, "
            f"allowed: {list(CONSTRUCTOR_OPTIONS)}"
        )
        raise ValueError(msg)
    if not isinstance(value.get("name"), str) or not value["name"]:
        msg = f"{label}: constructor: 'name' (the classmethod) is required"
        raise ValueError(msg)
    value = dict(value)
    if "requires" in value:
        value["requires"] = permission_names(value["requires"], "constructor.requires")
    return value


def check_names(cls, layer, extra_properties=()):
    """Catch typos: each listed property must be a property of ``cls`` or
    one of ``extra_properties``, each listed method one of its functions, and
    a named constructor one of its classmethods."""
    if not isinstance(layer, dict):
        return
    constructor = layer.get("constructor")
    if isinstance(constructor, dict) and constructor["name"] != DEFAULT_CONSTRUCTOR:
        member = inspect.getattr_static(cls, constructor["name"], None)
        if not isinstance(member, classmethod):
            msg = f"{cls.__name__}.{constructor['name']} is not a classmethod (constructor)"
            raise ValueError(msg)
    for name in layer.get("properties", {}):
        if name in extra_properties:
            continue
        if not isinstance(inspect.getattr_static(cls, name, None), property):
            known = sorted(
                {*extra_properties, *(n for n in dir(cls) if _is_property(cls, n))}
            )
            msg = f"{cls.__name__} has no property {name!r}; properties: {known}"
            raise ValueError(msg)
    for name in layer.get("methods", {}):
        if not inspect.isfunction(inspect.getattr_static(cls, name, None)):
            msg = f"{cls.__name__}.{name} is not a method"
            raise ValueError(msg)


def _is_property(cls, name):
    try:
        return isinstance(inspect.getattr_static(cls, name), property)
    except AttributeError:
        return False


def set_class_keyword(cls, value, *, extra_properties=()):
    """Store the ``mcp=`` class keyword of ``cls`` (called from
    ``__init_subclass__``) and register the class. ``extra_properties`` are
    the names that count as properties besides Python properties."""
    layer = normalize_options(value, f"{cls.__name__}(mcp=...)")
    check_names(cls, layer, extra_properties)
    check_markers(cls)
    if layer is not None:
        setattr(cls, KEYWORD_ATTR, layer)
    register_class(cls)


def describe_class(cls, declare, options, *, extra_properties=()):
    """
    Implement ``Cls.mcp_describe(declare, **options)``: store a declaration
    for ``cls`` when one is given (once per class), then return
    :func:`class_options`. ``extra_properties`` is that of
    :func:`set_class_keyword`.
    """
    if declare is not None and options:
        msg = "mcp_describe() takes True, False or options, not both"
        raise TypeError(msg)
    value = declare if declare is not None else (options or None)
    if value is not None:
        if DESCRIBED_ATTR in vars(cls):
            msg = (
                f"{cls.__name__}.mcp_describe() already set what agents see of "
                f"{cls.__name__}; call it with options once per class"
            )
            raise ValueError(msg)
        layer = normalize_options(value, f"{cls.__name__}.mcp_describe()")
        check_names(cls, layer, extra_properties)
        setattr(cls, DESCRIBED_ATTR, layer)
        changed()
    return class_options(cls)


def class_options(cls):
    """
    The effective options of ``cls``, as a plain dict:

    - ``declared``: True when a keyword or ``mcp_describe()`` declares the
      class, False when it is hidden, and None when only its markers can make
      it visible.
    - ``description``: the class's own description (never inherited), or None.
    - ``all_methods``, ``methods`` and ``properties``: combined from the base
      classes down.
    - ``constructor``: the nearest declaration up the class hierarchy,
      looking on each class at its ``mcp_describe()``, then its keyword, then
      its ``@mcp.constructor``. It is False, None (no constructor) or
      ``{"name", "description", "requires"}``, where the name "default"
      stands for ``cls(server, **values)``.
    """
    result = {
        "declared": None,
        "description": None,
        "all_methods": False,
        "methods": {},
        "properties": {},
        "constructor": _nearest_constructor(cls),
    }

    for klass in reversed(cls.__mro__):
        own = vars(klass)
        for layer in (own.get(KEYWORD_ATTR), own.get(DESCRIBED_ATTR)):
            if layer is None:
                continue
            if layer is False:
                result["declared"] = False
                continue
            result["declared"] = True
            result["all_methods"] = layer.get("all_methods", result["all_methods"])
            result["methods"] = {**result["methods"], **layer.get("methods", {})}
            result["properties"] = {
                **result["properties"],
                **layer.get("properties", {}),
            }

    own = vars(cls)
    for layer in (own.get(DESCRIBED_ATTR), own.get(KEYWORD_ATTR)):
        if isinstance(layer, dict) and "description" in layer:
            result["description"] = layer["description"]
            break
    return result


def _nearest_constructor(cls):
    for klass in cls.__mro__:
        own = vars(klass)
        for layer in (own.get(DESCRIBED_ATTR), own.get(KEYWORD_ATTR)):
            if isinstance(layer, dict) and "constructor" in layer:
                return layer["constructor"]
        for name, options in marked_constructors(klass).items():
            return {"name": name, **options}
    return None


def default_constructor_problem(cls):
    """Why ``cls(server, **values)`` cannot create an instance of ``cls``, or
    None. ``values`` holds any of the class's exposed, writable fields, so
    the call must work with none of them and with all of them."""
    values = [
        name
        for name, field in cls._mcp_fields().items()
        if isinstance(field.options, dict) and not field.options.get("read_only")
    ]
    try:
        signature = inspect.signature(cls)
    except (TypeError, ValueError):  # Python cannot read it: let the call tell
        return None
    try:
        signature.bind(None)
        signature.bind(None, **dict.fromkeys(values))
    except TypeError as error:
        given = ", **values" if values else ""
        return (
            f"{cls.__name__}(server{given}) does not match its __init__ ({error}); "
            f"mark a classmethod with @mcp.constructor, or set constructor=False"
        )
    return None


# -----------------------------------------------------------------------------
# Classes whose instances agents reach
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    """
    A field of an exposable class: a value stored on the instance, which
    agents read with ``getattr`` and write with ``setattr``. Setting a field
    cannot fail, so ``object_update`` sets every field it is given before it
    runs any property setter.
    """

    name: str
    type_def: object  # the declared type, None if it cannot be resolved
    # What agents see of it (PROPERTY_OPTIONS, read_only decided), None when
    # not exposed, or False when hidden on purpose (no startup warning)
    options: dict | bool | None
    nullable: bool = False  # may hold None as well as values of type_def
    holds_objects: bool = False  # may hold objects agents reach (written by id)


@dataclass(frozen=True)
class Constructor:
    """How agents create instances of an exposable class, in a ``new`` step
    of ``object_batch``."""

    attr: str | None = None  # a classmethod taking the server first; None: the default
    description: str = ""
    requires: tuple = ()  # the permissions creating one needs
    problem: str | None = None  # why it cannot work: warned about, not offered


class MCPExposable:
    """
    Lets agents reach the instances of a class through the trame server's
    object tools (``object_get``, ``object_update``, ``object_call``...).

    A class that inherits it declares what agents see with the ``mcp=``
    class keyword, :meth:`mcp_describe`, ``@mcp.method``, ``@mcp.property``
    and ``@mcp.constructor``. An instance is exposed with :meth:`mcp_expose`, or
    with ``server.mcp.expose_object()``. ``TrameComponent`` and
    trame-dataclass's ``StateDataModel`` inherit it, and it can be mixed into
    any class: it has no ``__init__`` and keeps no state besides a lazy
    ``_id``.

    The ``_mcp_*`` members are what the server asks of a class. Their
    defaults describe a plain class, with Python properties and methods
    only. A package that brings its own type of class overrides them on its
    base class, as trame-dataclass does for fields.
    """

    # Top-level packages whose classes make up the API of this type of class:
    # agents never see the members a class inherits from them, and marking or
    # listing one is an error. The server combines those of the whole MRO.
    _mcp_api_packages = ("trame_common",)

    # Whether an object name holds the instance weakly, freeing the name when
    # the instance is collected: for classes whose instances something else
    # keeps alive while in use, as components are by the callbacks they bind.
    _mcp_hold_weakly = False

    def __init_subclass__(cls, mcp=None, **kwargs):
        super().__init_subclass__(**kwargs)
        set_class_keyword(cls, mcp, extra_properties=cls._mcp_field_names())

    @classmethod
    def mcp_describe(cls, declare=None, /, **options):
        """
        Set what agents see of this class, when it comes from another library,
        with the options of the ``mcp=`` class keyword (``description``,
        ``all_methods``, ``methods``, ``properties``, ``constructor``), or
        False to hide it. The
        settings apply to the whole process and to subclasses, and only one call
        per class may change them.

        Every call returns the class's effective options as plain data;
        ``server.mcp.describe(cls)`` shows what agents see.
        """
        return describe_class(
            cls, declare, options, extra_properties=cls._mcp_field_names()
        )

    def mcp_expose(self, name, *, description=None, read_only=False):
        """
        Expose this instance to agents under ``name``, on its ``server``. An
        instance may have several names, each with its own description. On a
        child server, the name goes through the server's translator, as state
        keys do.

        With ``read_only``, agents can only call its read-only methods and
        cannot write its properties, whichever way they reach it, unless a
        writable name, or a property of a writable object, also reaches it.

        An instance without a server is exposed with
        ``server.mcp.expose_object(instance, name)`` instead.

        Keyword arguments:
        name -- a name starting with a letter or an underscore, not already used
        description -- what this instance is for in the app (default None)
        read_only -- agents may only read it (default False)
        """
        self._mcp_server().expose_object(
            self, name, description=description, read_only=read_only
        )

    def mcp_unexpose(self):
        """Withdraw every name exposing this instance"""
        self._mcp_server()._remove_object(self)

    def _mcp_server(self):
        server = getattr(self, "server", None)
        if server is None:
            msg = (
                f"{type(self).__name__} {self._id} has no trame server; expose it "
                f"with server.mcp.expose_object() instead"
            )
            raise RuntimeError(msg)
        return server.mcp

    @property
    def _id(self):
        """This instance's process-wide unique id, made when first read, from
        the generator every type of object agents reach shares, so their ids
        never collide."""
        try:
            return self.__dict__["_trame_mcp_id"]
        except KeyError:
            return self.__dict__.setdefault("_trame_mcp_id", next_id())

    # What the server asks: a package's base class overrides these

    @classmethod
    def _mcp_field_names(cls):
        """The names of the class's fields, which ``properties=`` may list
        besides Python properties. Called when the class is defined, so it
        cannot depend on what the class declares."""
        return ()

    @classmethod
    def _mcp_fields(cls):
        """``{name: Field}`` for every field of the class, in definition
        order, a base's first. The rules and options of this type of class
        apply here, and so does the class's ``properties=`` option for these
        names (:func:`class_options`): the server reads only
        ``Field.options``."""
        return {}

    @classmethod
    def _mcp_constructor(cls):
        """How agents create instances, as a :class:`Constructor`, or None
        when they cannot: from the ``constructor`` option or the
        ``@mcp.constructor`` marker. The default constructor,
        ``cls(server, **values)``, takes the exposed, writable fields."""
        option = class_options(cls)["constructor"]
        if not option:  # None (not declared) or False (turned off)
            return None
        default = option["name"] == DEFAULT_CONSTRUCTOR
        return Constructor(
            attr=None if default else option["name"],
            description=option.get("description") or "",
            requires=tuple(option.get("requires", ())),
            problem=default_constructor_problem(cls) if default else None,
        )

    async def _mcp_settle(self):
        """Wait until the work a change started has finished, such as
        watchers, so that the reply and the agent's next read reflect it. The
        server calls it after every update, method call and creation, and logs
        what it raises: the change itself was applied."""


# -----------------------------------------------------------------------------
# Progress of a long call
# -----------------------------------------------------------------------------


class Progress:
    """Reports to an agent how far its long call has got.

    Declare a parameter of this type on an async tool or method, with None
    as its default::

        @mcp.method
        async def load(self, path: str, progress: Progress | None = None) -> str:
            ...
            if progress:
                await progress(done, total=count, message=f"Read {done} blocks")

    Agents don't see the parameter. When an agent calls the method, trame
    passes a reporter in it, which does nothing if the agent asked for no
    progress. When the application calls the method itself, the parameter
    keeps its default.

    ``value`` must increase from one report to the next, and ``total`` and
    ``message`` are optional. Reports that arrive faster than a client can use
    them are combined, and reports made after the call returns are ignored.
    """

    async def __call__(self, value, total=None, message=None):
        """Report ``value``, out of ``total`` when it is known, with a ``message``
        saying what is happening. This base class reports nothing."""
