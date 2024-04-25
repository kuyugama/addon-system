import importlib
import sys
import types
from pathlib import Path, PosixPath
from typing import TypeVar, ClassVar, Type

T = TypeVar("T")
C = ClassVar["C"]


class FirstParamSingletonSingleton(type):
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
            instance = super(FirstParamSingletonSingleton, cls).__call__(
                *args, **kwargs
            )
            by_param[param] = instance

        return instance


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


def transform_to_library_version(raw_version: str | int | float):
    if isinstance(raw_version, (int, float)):
        return str(raw_version)

    version = ""
    for char in raw_version:
        if char != "*":
            version += char
        else:
            version = version[:-1]
            break

    if len(version.split(".")) < 2:
        version += ".0"

    return version


def validate_version(version: str | int | float):
    if isinstance(version, (int, float)):
        return True

    if not len(version):
        return False

    if version.startswith("."):
        return False

    if version.isdigit() or version == "*":
        return True

    if all(map(lambda x: x != "", version.split("."))):
        return True


def check_version(
    required_version: str | int | float, library_version: str | int | float
):
    if not validate_version(required_version):
        raise ValueError(
            "Unsupported required version type: {}".format(required_version)
        )
    elif not validate_version(library_version):
        raise ValueError("Unsupported library version type: {}".format(library_version))

    if isinstance(required_version, (int, float)):
        required_version = str(required_version)

    if isinstance(library_version, (int, float)):
        library_version = str(library_version)

    required_version_parted = required_version.split(".")
    library_version_parted = library_version.split(".")

    if len(required_version_parted) > len(library_version_parted):
        return False

    for part_req, part_lib in zip(required_version_parted, library_version_parted):
        if part_req == part_lib:
            continue
        elif part_req == "*":
            return True
        else:
            return False

    return True
