import builtins
import functools
import importlib
import inspect
import sys
import types
import warnings
from contextlib import contextmanager
from pathlib import Path, PosixPath
from typing import TypeVar, Type, cast

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
            instance = super(FirstParamSingletonMeta, cls).__call__(*args, **kwargs)
            by_param[param] = instance

        return instance


class FirstParamSingleton(metaclass=FirstParamSingletonMeta):
    """Singleton as a normal base class"""


root = Path().absolute()


def get_module_import_path(path_to_module: Path) -> str:
    relative_path = path_to_module.relative_to(root)

    if isinstance(relative_path, PosixPath):
        return str(relative_path).replace("/", ".")
    else:
        return str(relative_path).replace("\\", ".")


def recursive_reload_module(
    module: types.ModuleType, exclude: tuple[str] = ...
) -> types.ModuleType:
    if not isinstance(module, types.ModuleType):
        raise ValueError("Unsupported type of module")

    if not isinstance(exclude, tuple):
        exclude = ()

    exclude += (*sys.builtin_module_names, "os", "builtins", "__main__", "ntpath")

    if module.__name__ in exclude:
        return module

    for value in vars(module).values():
        if not isinstance(value, types.ModuleType):
            continue

        recursive_reload_module(value, exclude)

    return importlib.reload(module)


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
                "{} is deprecated since {}: {}".format(func.__name__, version, msg),
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter("default", DeprecationWarning)  # reset warning filter

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


def resolve_runtime(cls: type[T], name: str = None) -> T:
    """
    Helper function for addon modules. Resolves name from builtins

    :param cls: Type of the variable to be resolved
    :param name: Name of the builtin variable (can be automatically set by the code context)
    """
    called_from = inspect.stack()[1]

    if called_from.function != "<module>":
        raise RuntimeError(
            "resolve_runtime can be called only at module level. Not in a function"
        )

    if name is None:
        # Get a name of the variable
        name = called_from.code_context[-1].split("=", 1)[0].strip()

    if not hasattr(builtins, name):
        raise NameError(f'Requested "{name}" is not provided by addon loader')

    value = getattr(builtins, name)

    if not isinstance(value, cls):
        raise TypeError(
            f'Name "{name}" contains {type(value)}, but requested type is {cls}'
        )

    return cast(cls, value)
