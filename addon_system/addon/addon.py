from typing import Union, TypeVar, overload
from abc import abstractmethod
from pathlib import Path
import importlib
import string
import types
import time
import os

from addon_system.libraries.base_manager import BaseLibManager
from .interface import ModuleInterface, unload_module
from .namespace import AddonNamespace
from addon_system import utils
from . import meta

from addon_system.errors import (
    AddonSystemException,
    AddonImportError,
    AddonInvalid,
)

try:
    import pybaked

    pybaked_installed = True
except ImportError:
    pybaked_installed = False

ModuleInterfaceType = TypeVar("ModuleInterfaceType", bound="ModuleInterface")


def _unique_baked_file_name(directory_path: Path, origin: str) -> Path:
    # Generate unique name using timestamp in hex
    time_hex = hex(int(time.time()))[2:]
    base_name = origin.split(".", 1)[0] + "_" + time_hex

    name = base_name

    copy_number = 1
    # If that name already exists (how?) - add number of the copy to it
    while (directory_path / (name + pybaked.protocol.EXTENSION)).exists():
        name = base_name + "_" + hex(copy_number)[2:]
        copy_number += 1

    return directory_path / name


class AbstractAddon(utils.ABCFirstParamSingleton):
    """Addon wrapper class. Semi-independent part of AddonSystem"""

    @staticmethod
    @abstractmethod
    def validate_name(name: str) -> bool:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def validate_path(path: Path) -> bool:
        raise NotImplementedError

    def __init__(self, path: Path, meta_path: Path = None) -> None:
        if not path.exists():
            raise AddonInvalid("Path doesn't exists")

        if not self.validate_name(path.name):
            raise AddonInvalid("Name invalid")

        from addon_system import AddonSystem
        from addon_system.addon.storage import AddonStorage

        self._path = path
        self._meta_path = meta_path or path

        self._meta: meta.AbstractAddonMeta = meta.factory(self._meta_path)

        self._module: types.ModuleType | None = None
        self._interface: ModuleInterface | None = None

        self._system: AddonSystem | None = None
        self._storage: AddonStorage | None = None

        self._namespace: AddonNamespace = AddonNamespace(self)

    def install_system(self, system) -> None:
        from addon_system import AddonSystem

        if not isinstance(system, AddonSystem):
            raise TypeError("Expected AddonSystem, but got {}".format(type(system)))

        if not self._path.is_relative_to(system.root):
            raise AddonSystemException(
                "Addon is not owned by system that you tried to install to addon"
            )

        self._system = system

    def is_in_root(self, system) -> bool:
        from addon_system import AddonSystem

        if not isinstance(system, AddonSystem):
            raise TypeError("Expected AddonSystem, but got {}".format(type(system)))

        return self._path.is_relative_to(system.root)

    @abstractmethod
    def module(
        self,
        lib_manager: BaseLibManager = None,
        reload: bool = False,
        builtin_injection: bool = False,
    ) -> types.ModuleType:
        """
        Returns addon's main module.

        Import's if not, reloads if ``reload`` set to True.

        If not system installed - requires ``lib_manager`` to be passed

        If dependencies is not satisfied - raises AddonImportError

        To set names that can be accessed through module -
        update namespace property contents

        :param lib_manager: Library manager, that will
                be used to check addon's dependencies
        :param reload: Whether reload addon's main module or not
        :param builtin_injection: Whether inject namespace values to builtins (Optional and deprecated since 1.2.19, will be removed at 1.3.0)

        :return: Addon's main module
        """
        raise NotImplementedError

    @overload
    def interface(self, cls: None = None, lib_manager: BaseLibManager = None) -> ModuleInterface: ...

    @overload
    def interface(self, cls: type[ModuleInterfaceType], lib_manager: BaseLibManager = None) -> ModuleInterfaceType: ...

    def interface(
        self, cls: type[ModuleInterfaceType] = ModuleInterface, lib_manager: BaseLibManager = None
    ) -> ModuleInterfaceType:
        """
        Creates ModuleInterface for this addon

        Use addon.module() first if this addon created without AddonSystem,
        or you need to set values that can be accessed on module evaluation

        **Note**: Only one interface can be set to the addon!
        Other attempts will return already set interface

        :param cls: ModuleInterface subclass
        :param lib_manager: Library manager, that will be used to check addon's dependencies before module load
        :return: module interface instance
        """
        if not issubclass(cls, ModuleInterface):
            raise TypeError(f"Invalid ModuleInterface type provided: {cls}")

        # If type of set interface is not equal to provided - raise exception
        if self._interface is not None and self._interface.module_loaded and type(self._interface) is not cls:
            raise AddonSystemException(
                f"Provided {cls} interface, but addon already uses interface of type {self._interface.__class__}"
            )

        if self._interface is not None and type(self._interface) is cls:
            return self._interface

        if self._system is None and not lib_manager:
            raise AddonSystemException(
                "To load addon module into module interface system or lib_manager must be provided"
            )

        self._interface = cls(self, lib_manager)

        return self._interface

    def unload_interface(self, *args, **kwargs) -> None:
        """
        Unload addon's interface

        :param args: positional arguments to ``on_unload`` module method
        :param kwargs: keyword arguments to ``on_unload`` module method
        """
        if self._interface is None:
            return

        self._interface.unload(*args, **kwargs)
        self._interface = None

    def unload_module(self):
        """Tries to unload addon's module"""
        if self._module is None:
            return

        unload_module(self._module)

        self._module = None

    @abstractmethod
    def storage(self):
        """Get addon's key-value storage"""
        raise NotImplementedError

    def check_dependencies(self, lib_manager: BaseLibManager = None) -> bool:
        """
        Check addon dependencies

        :param lib_manager: required if system is
                not installed to addon(if system is installed its faster)
        :return: True if dependencies is satisfied
        """
        if lib_manager is None and self._system is None:
            raise AddonSystemException(
                "To check dependencies addon require lib_manager to be "
                "provided or system to be installed."
                "With installed library its function uses System's cache to "
                "reduce time"
            )

        if self._system is not None:
            # Use of cache reduces required time
            return self._system.check_dependencies(self)

        if lib_manager:
            return lib_manager.check_dependencies(self.metadata.depends)

    def satisfy_dependencies(self, lib_manager: BaseLibManager = None):
        if self._system is None and lib_manager is None:
            raise AddonSystemException(
                "To install dependencies addon require lib_manager to be "
                "provided or system to be installed"
            )

        if self._system:
            # Install dependencies using system and save installed libraries
            # to system's library manager
            return self._system.satisfy_dependencies(self)

        if lib_manager:
            # Install dependencies with user provided library manager
            return lib_manager.install_libraries(self.metadata.depends)

    def set_enabled(self, enabled: bool):
        """
        Change addon status via its instance. Requires AddonSystem to be installed

        :param enabled: new addon status
        """

        self.enabled = enabled

    def enable(self):
        """
        Enable addon via its instance. Requires AddonSystem to be installed.

        Shortcut for: ::

            addon.enabled = True

        """
        self.enabled = True

    def disable(self):
        """
        Disable addon via its instance. Requires AddonSystem to be installed.

        Shortcut for: ::

            addon.enabled = False

        """
        self.enabled = False

    @property
    def path(self):
        """Get addon's path"""
        return self._path

    @property
    def namespace(self) -> AddonNamespace:
        """Get addon's namespace"""
        return self._namespace

    @property
    @utils.deprecated(
        "module_names was renamed to namespace and will be removed in 1.3.0",
        version="1.2.10",
    )
    def module_names(self):
        return self._namespace

    @property
    def system(self):
        """Get addon's installed system"""
        return self._system

    @property
    def enabled(self):
        """Check addon's enabled status"""
        if self._system is None:
            raise AddonSystemException(
                "To check addon status via its instance you must install system's instance to it"
            )

        return self._system.get_addon_enabled(self)

    @enabled.setter
    def enabled(self, enabled: bool) -> None:
        """Set addon's enabled status"""
        if self._system is None:
            raise AddonSystemException(
                "To change addon status via its instance you must install system's instance to it"
            )

        if not isinstance(enabled, bool):
            raise TypeError("Addon status must be bool type")

        self._system.set_addon_enabled(self, enabled)

    @property
    def metadata(self) -> meta.AbstractAddonMeta:
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

    @abstractmethod
    def bake_to_file(self, path: str | Path = None) -> Path:
        """
        "Bake" this addon to file using ``pybaked`` library

        :return: "baked" addon file path
        """
        raise NotImplementedError

    @abstractmethod
    def bake_to_bytes(self) -> bytes:
        """
        "Bake" this addon to bytes using ``pybaked`` library

        :return: "baked" addon bytes
        """
        raise NotImplementedError

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
        return (
            f"{type(self).__name__}"
            f"<{self.metadata.id}>"
            f"(name={self.metadata.name!r}, path={str(self._path)!r})"
        )


class Addon(AbstractAddon):
    """Class-wrapper of addon. Semi-independent part of AddonSystem"""

    @staticmethod
    def validate_path(path: Path) -> bool:
        """Validates addon's path"""
        return (
            path.is_dir()
            and Addon.validate_name(path.name)
            and meta.AddonMeta.validate_path(path / "addon.json")
        )

    @staticmethod
    def validate_directory_name(name: str) -> bool:
        """
        Validate addon's directory name

        :returns: ``bool``
        """
        return Addon.validate_name(name)

    @staticmethod
    def validate_name(name: str) -> bool:
        """Validates addon's name (Path.name)'"""
        for char in name:
            if char not in string.ascii_letters:
                return False
        return True

    def __init__(self, path: Path):
        if not self.validate_path(path):
            raise AddonInvalid("Invalid addon path")

        super().__init__(path, path / "addon.json")

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
            return utils.reload_addon_modules(self)

        return importlib.import_module(self.module_import_path)

    def module(
        self,
        lib_manager: BaseLibManager = None,
        reload: bool = False,
        builtin_injection: bool = False,
    ) -> types.ModuleType:

        if self._module and not reload:
            return self._module

        if not self.check_dependencies(lib_manager):
            raise AddonImportError("Addon dependencies is not satisfied")

        if not self._namespace.empty() and builtin_injection:
            utils.warn_deprecated(
                "Value injection via builtins is deprecated since 1.2.19 and will be removed in 1.3.0"
            )
            with utils.replace_builtins(**self._namespace.raw()):
                module = self._import(reload=reload)

            for name, value in self._namespace.items():
                setattr(module, name, value)
        else:
            module = self._import(reload=reload)

        self._module = module

        return self._module

    def storage(self):
        """Get addon's key-value storage"""
        from addon_system.addon.storage import AddonStorage

        if self._storage:
            return self._storage

        self._storage = AddonStorage(self)

        return self._storage

    def bake_to_file(self, path: str | Path = None) -> Path:
        """
        "Bake" this addon to file using ``pybaked`` library

        :return: "baked" addon file path
        """
        if not pybaked_installed:
            raise ValueError("pybaked is not installed")

        import pybaked

        if path is None:
            path = _unique_baked_file_name(Path(), self.metadata.name)

        return pybaked.BakedMaker.from_package(
            self.path, hash_content=True, metadata=self.metadata.dict()
        ).file(path)

    def bake_to_bytes(self) -> bytes:
        """
        "Bake" this addon to bytes using ``pybaked`` library

        :return: "baked" addon bytes
        """
        if not pybaked_installed:
            raise ValueError("pybaked is not installed")

        import pybaked

        return pybaked.BakedMaker.from_package(
            self.path, hash_content=True, metadata=self.metadata.dict()
        ).bytes()


supported: list[type[AbstractAddon]] = [Addon]

if pybaked_installed:
    import pybaked

    class BakedAddon(AbstractAddon):
        @staticmethod
        def validate_name(name: str) -> bool:
            return name.endswith(".py.baked") and name.split(".", 1)[0].isidentifier()

        @staticmethod
        def validate_path(path: Path) -> bool:
            return path.is_file() and BakedAddon.validate_name(path.name)

        def __init__(self, path: Path):
            super().__init__(path)

        @property
        def module_import_path(self):
            package_path = self.path.with_name(self.path.name.split(".", 1)[0])

            path = (package_path / self.metadata.module).with_suffix("")

            if path.name == "__init__":
                path = path.parent

            return utils.get_module_import_path(path)

        def _import(self, reload: bool = False) -> types.ModuleType:
            if reload and self._module:
                return utils.reload_addon_modules(self)

            pybaked.loader.init()

            return importlib.import_module(self.module_import_path)

        def module(
            self,
            lib_manager: BaseLibManager = None,
            reload: bool = False,
            builtin_injection: bool = False,
        ) -> types.ModuleType:
            if not reload and self._module:
                return self._module

            if not self.check_dependencies(lib_manager):
                raise AddonImportError("Addon dependencies is not satisfied")

            if not self._namespace.empty() and builtin_injection:
                utils.warn_deprecated(
                    "Value injection via builtins is deprecated since 1.2.19 and will be removed in 1.3.0"
                )
                with utils.replace_builtins(**self._namespace.raw()):
                    module = self._import(reload=reload)

                for name, value in self._namespace.items():
                    setattr(module, name, value)
            else:
                module = self._import(reload=reload)

            self._module = module

            return self._module

        def storage(self):
            raise AddonInvalid("Baked addons doesn't support storages yet")

        def bake_to_file(self, path: str | Path = None) -> Path:
            """
            Copies this file and returns path to copy
            """

            if path is None:
                path = _unique_baked_file_name(Path(), self.path.name.split(".", 1)[0])

            return (
                pybaked.BakedReader(self.path)
                .to_maker()
                .update_metadata(self.metadata.dict())
                .file(path)
            )

        def bake_to_bytes(self) -> bytes:
            """
            Reads this file bytes and returns it
            """

            return (
                pybaked.BakedReader(self.path)
                .to_maker()
                .update_metadata(self.metadata.dict())
                .bytes()
            )

    supported.append(BakedAddon)


def factory(path: Path) -> AbstractAddon:
    """
    Makes addon instance depend on path

    :return: AbstractAddon subclass
    """
    for cls in supported:
        if cls.validate_path(path):
            return cls(path)
