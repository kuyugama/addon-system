import importlib
import os
import string
import types
from pathlib import Path
from typing import Union, Any, TypeVar

from addon_system import utils
from addon_system.errors import (
    AddonInvalid,
    AddonSystemException,
    AddonImportError,
)
from addon_system.libraries.base_manager import BaseLibManager
from addon_system.utils import FirstParamSingleton
from .interface import ModuleInterface, unload_module
from .meta import AddonMeta

ModuleInterfaceType = TypeVar("ModuleInterfaceType", bound="ModuleInterface")


class Addon(FirstParamSingleton):
    """Class-wrapper of addon. Semi-independent part of AddonSystem"""

    _by_path: dict[Path, "Addon"] = {}

    @staticmethod
    def validate_directory_name(name: str) -> bool:
        """
        Validate addon's directory name

        :returns: ``bool``
        """
        for char in name:
            if char not in string.ascii_letters:
                return False
        return True

    def __init__(self, path: Path):
        if not path.exists():
            raise AddonInvalid("Addon at this path does not exists")

        if not path.is_dir():
            raise AddonInvalid("Addons must be dirs")

        if not self.validate_directory_name(path.name):
            raise AddonInvalid(
                "Addon dir name can contain only ascii letters and be in CamelCase"
            )

        from addon_system.addon.storage import AddonStorage
        from addon_system import AddonSystem

        meta = AddonMeta(path / "addon.json")

        self._path = path
        self._meta = meta

        self._module: types.ModuleType | None = None
        self._interface: ModuleInterface | None = None

        self._storage: AddonStorage | None = None
        self._system: AddonSystem | None = None

        self._module_names: dict[str, Any] = {}

    def install_system(self, system):
        from addon_system import AddonSystem

        if not isinstance(system, AddonSystem):
            return

        if not self.path.is_relative_to(system.root):
            raise AddonSystemException(
                "Addon is not owned by system that you tried to install to addon"
            )

        self._system = system

    @property
    def module_names(self):
        return self._module_names

    @property
    def system(self):
        return self._system

    @property
    def enabled(self) -> bool:
        if self._system is None:
            raise AddonSystemException(
                "To check addon status you must install AddonSystem"
            )

        return self._system.get_addon_enabled(self)

    @property
    def path(self):
        return self._path

    @property
    def metadata(self):
        """Addon's metadata"""
        return self._meta

    @property
    def update_time(self) -> float:
        """
        Addon update time.
        Return max of directory update time and metafile update time,
        sometimes directories do not flush
        when updating files within it
        """
        return max(os.path.getmtime(self._path), self.metadata.update_time)

    @property
    def module_path(self) -> Path:
        return self._path / self.metadata.module

    @property
    def module_import_path(self) -> str:
        path = self.module_path
        if path.name.endswith(".py"):
            path = path.parent / path.name[:-3]

        if path.name == "__init__":
            path = path.parent

        return utils.get_module_import_path(path)

    def _import(self, reload: bool = False) -> types.ModuleType:
        """Imports or reloads addon's module"""
        if reload and self._module:
            return utils.recursive_reload_module(self._module)

        return importlib.import_module(self.module_import_path)

    def module(
        self,
        lib_manager: BaseLibManager = None,
        reload: bool = False,
        replace_names: dict[str, Any] = None,
    ) -> types.ModuleType:
        """
        Import addon's main module or reload it. Requires dependencies to be satisfied

        :param lib_manager: Library manager (dependency check)
        :param reload: Module will be reloaded if True
        :param replace_names: Replace built-in names
                when module imports. Don't recommend if module
                contains blocking code(``time.sleep(...)``, etc.), and you use threading.
                Also sets these names as attributes to module instance and addon.module_names
                from which ``utils.resolve_runtime()`` function gets values
        """

        if self._module and not reload:
            return self._module

        if not self.check_dependencies(lib_manager):
            raise AddonImportError("Addon dependencies is not satisfied")

        if (
            replace_names is not None
            and isinstance(replace_names, dict)
            or self._module_names
        ):
            if replace_names:
                self._module_names.update(replace_names)

            with utils.replace_builtins(**self._module_names):
                module = self._import(reload=reload)

            for name, value in self._module_names.items():
                setattr(module, name, value)
        else:
            module = self._import(reload=reload)

        self._module = module

        return self._module

    def interface(
        self, cls: type[ModuleInterfaceType], *load_args, **load_kwargs
    ) -> ModuleInterfaceType:
        """
        Creates ModuleInterface for this addon

        Use addon.module() first if this addon created without AddonSystem,
        or you need to set values that can be accessed on module evaluation

        **Note**: Only one interface can be set to the addon!
        Other attempts will return already set interface

        :param cls: ModuleInterface subclass
        :param load_args: positional arguments that will be passed to on_load module method
        :param load_kwargs: keyword arguments that will be passed to on_load module method

        :return: module interface instance
        """
        if not issubclass(cls, ModuleInterface):
            raise TypeError(f"Invalid ModuleInterface type provided: {cls}")

        if self._interface is not None and self._interface.module_loaded:
            return self._interface

        self._interface = cls(self, *load_args, **load_kwargs)

        return self._interface

    def unload_interface(self, *args, **kwargs):
        """
        Tries to unload interface

        All arguments will be passed to on_unload module method
        """
        if self._interface is None:
            return

        self._interface.unload(*args, **kwargs)
        self._interface = None

    def unload_module(self):
        """Tries to unload module"""
        if self._module is None:
            return

        unload_module(self._module)
        self._module = None

    def storage(self):
        """Get addon's key-value storage"""
        from addon_system.addon.storage import AddonStorage

        if self._storage:
            return self._storage

        self._storage = AddonStorage(self)

        return self._storage

    def check_dependencies(self, lib_manager: BaseLibManager = None) -> bool:
        """
        Check addon dependencies
        :param lib_manager: required if system is not installed to addon(if system is installed its faster)
        :return: True if dependencies is satisfied
        """
        if lib_manager is None and self._system is None:
            raise AddonSystemException(
                "To check dependencies addon require lib_manager to be provided or system to be installed. "
                "With installed library its function uses System's cache to reduce time"
            )

        if self._system is not None:
            # Use of cache reduces required time
            return self._system.check_dependencies(self)

        if lib_manager:
            return lib_manager.check_dependencies(self.metadata.depends)

    def satisfy_dependencies(self, lib_manager: BaseLibManager = None):
        if self._system is None and lib_manager is None:
            raise AddonSystemException(
                "To install dependencies addon require lib_manager to be provided or system to be installed"
            )

        if self._system:
            # Install dependencies using system and save installed libraries to system's library manager
            return self._system.satisfy_dependencies(self)

        if lib_manager:
            # Install dependencies with user provided library manager
            return lib_manager.install_libraries(self.metadata.depends)

    def set_enabled(self, enabled: bool):
        """
        Change addon status via its instance. Requires AddonSystem to be installed

        :param enabled: new addon status
        """
        if self._system is None:
            raise AddonSystemException(
                "To change addon status via its instance you must install system's instance to it"
            )
        self._system.set_addon_enabled(self, enabled)

    def enable(self):
        """
        Enable addon via its instance. Requires AddonSystem to be installed.

        Shortcut for: ::

            set_addon_enabled(True)

        """
        self.set_enabled(True)

    def disable(self):
        """
        Disable addon via its instance. Requires AddonSystem to be installed.

        Shortcut for: ::

            set_addon_enabled(False)

        """
        self.set_enabled(False)

    def __eq__(self, other: Union[str, "Addon"]) -> bool:
        if isinstance(other, str):
            return self.metadata.id == other
        elif isinstance(other, Addon):
            return self is other or self.metadata.id == other.metadata.id
        else:
            return False

    def __hash__(self) -> int:
        return hash(self._path)

    def __str__(self):
        return f"Addon<{self.metadata.id}>(name={self.metadata.name!r}, path={str(self._path)!r})"
