import importlib
import os
import string
from pathlib import Path

from addon_system import utils
from addon_system.addon.meta import AddonMeta
from addon_system.errors import (
    AddonInvalid,
    AddonSystemException,
    AddonImportError,
)
from addon_system.libraries.base_manager import BaseLibManager
from addon_system.utils import FirstParamSingletonSingleton


class Addon(metaclass=FirstParamSingletonSingleton):
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

        self._module = None

        self._storage: AddonStorage | None = None
        self._system: AddonSystem | None = None

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
        """Last addon update timestamp"""
        return os.path.getmtime(self._path)

    @property
    def module_path(self) -> Path:
        return self._path / self.metadata.module

    @property
    def module_import_path(self) -> str:
        path = self.module_path
        if path.name.endswith(".py"):
            path = path.parent / path.name[:-3]
        return utils.get_module_import_path(path)

    def module(self, lib_manager: BaseLibManager = None, reload: bool = False):
        """Import addon's main module or reload it. Requires dependencies to be satisfied"""

        if self._module and not reload:
            return self._module

        if not self.check_dependencies(lib_manager):
            raise AddonImportError("Addon dependencies is not satisfied")

        if reload:
            return utils.recursive_reload_module(self._module)

        self._module = importlib.import_module(self.module_import_path)

        return self._module

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
            self._system.satisfy_dependencies(self)

        if lib_manager:
            # Install dependencies with user provided library manager
            lib_manager.install_libraries(self.metadata.depends)

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

    def __str__(self):
        return f"Addon<{self.metadata.id}>(name={self.metadata.name!r}, path={str(self._path)!r})"
