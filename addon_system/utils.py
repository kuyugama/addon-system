import builtins
import functools
from abc import ABCMeta
from hashlib import sha256
import importlib
import inspect
from operator import methodcaller
import sys
import types
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar, Type, cast, Optional

from addon_system.errors import AddonSystemException

T = TypeVar("T")


class FirstParamSingletonMeta(type):
    def __call__(cls: Type[T], *args, **kwargs) -> T:
        if not hasattr(cls, "_by_param"):
            setattr(cls, "_by_param", {})

        by_param = getattr(cls, "_by_param", {})

        if len(args) == 0:
            param = None
        else:
            param = args[0]

        if param in by_param:
            instance = by_param[param]
            if hasattr(instance, "__reinit__"):
                instance.__reinit__(*args, **kwargs)
        else:
            instance = super(FirstParamSingletonMeta, cls).__call__(
                *args, **kwargs
            )
            by_param[param] = instance

        return instance


class ABCFirstParamSingletonMeta(FirstParamSingletonMeta, ABCMeta):
    def __call__(cls, *args, **kwargs):
        instance = super(FirstParamSingletonMeta, cls).__call__(*args, **kwargs)
        super(ABCMeta, cls).__call__(*args, **kwargs)

        return instance


class FirstParamSingleton(metaclass=FirstParamSingletonMeta):
    """Singleton as a normal base class"""


class ABCFirstParamSingleton(metaclass=ABCFirstParamSingletonMeta):
    """ABC + Singleton as a normal base class"""


project_root = Path(sys.path[0]).absolute()

# If running in interactive mode imports should be relative to working director
try:
    # If the pycharm python debug plugin is installed
    # and python is running using it - set the project_root
    # to current working directory
    import _pydev_runfiles  # noqa

    # This module is used only for check that pycharm debug plugin is installed
    del _pydev_runfiles

    if sys.path[0].endswith("pydev"):
        project_root = Path().absolute()

except ImportError:
    pass
if hasattr(sys, "ps1"):
    project_root = Path().absolute()


def get_module_import_path(path_to_module: Path) -> str:
    """Get an import path from a module file path"""
    return ".".join(path_to_module.relative_to(project_root).parts)


def recursive_reload_module(
    module: types.ModuleType, exclude: tuple[str] = ...
) -> types.ModuleType:
    if not isinstance(module, types.ModuleType):
        raise ValueError("Unsupported type of module")

    if not isinstance(exclude, tuple):
        exclude = ()

    exclude += (
        *sys.builtin_module_names,
        "os",
        "builtins",
        "__main__",
        "ntpath",
    )

    if module.__name__ in exclude:
        return module

    for value in vars(module).values():
        if not isinstance(value, types.ModuleType):
            continue

        recursive_reload_module(value, exclude)

    return importlib.reload(module)


def string_contains(parent: str, sub: str, case_sensitive: bool = True) -> bool:
    if not case_sensitive:
        sub = sub.lower()
        parent = parent.lower()

    return sub in parent


def string_iterable_contains(
    iterable: list[str], sub: str, case_sensitive: bool = True
) -> bool:
    if not case_sensitive:
        sub = sub.lower()
        iterable = map(methodcaller("lower"), iterable)

    return sub in iterable


def deprecated(msg: str, version: str):
    """
    Decorator that marks functions as deprecated

    :param msg: Message that will be shown in warning
    :param version: Deprecated since a version
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.simplefilter(
                "always", DeprecationWarning
            )  # turn off warning filter
            warnings.warn(
                "{} is deprecated since {}: {}".format(
                    func.__name__, version, msg
                ),
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter(
                "default", DeprecationWarning
            )  # reset warning filter

            return func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def replace_builtins(**names):
    """
    Replace builtins and cleanup changes
    :param names: builtins to be replaced
    """

    old_values = {}
    names_to_remove = []

    for name, value in names.items():
        if hasattr(builtins, name):
            old_values[name] = getattr(builtins, name)
        else:
            names_to_remove.append(name)

        setattr(builtins, name, value)

    try:
        yield

    finally:
        for name, value in old_values.items():
            setattr(builtins, name, value)

        for name in names_to_remove:
            delattr(builtins, name)


@functools.lru_cache
def hash_string_tuple(tuple_: tuple[str, ...]):
    hash_ = sha256()
    for string in tuple_:
        hash_.update(string.encode())

    return hash_.hexdigest()


@functools.lru_cache
def find_addon(path: Path | str) -> Optional["Addon"]:
    if isinstance(path, str):
        path = Path(path)

    if path.is_file():
        path = path.parent

    from addon_system import Addon

    # If this is the root of the filesystem - break
    while path != path.parent:
        try:
            return Addon(path)
        except AddonSystemException:
            path = path.parent


def resolve_runtime(cls: type[T], name: str = None) -> T:
    """
    Helper function for addon modules. Resolves name from builtins

    :param cls: Type of the variable to be resolved
    :param name: Name of the builtin variable (can be automatically set by the code context)
    """
    called_from = inspect.stack()[1]

    addon = find_addon(called_from.filename)

    if not addon:
        raise ValueError(
            "resolve_runtime can be called only from addon modules"
        )

    if name is None:
        # Get a name of the variable
        name = called_from.code_context[-1].split("=", 1)[0].strip()

    if name not in addon.namespace:
        raise NameError(f'Requested "{name}" is not provided by addon loader')

    value = addon.namespace[name]

    if not isinstance(value, cls):
        raise TypeError(
            f'Name "{name}" contains {type(value)}, but requested type is {cls}'
        )

    return cast(cls, value)
