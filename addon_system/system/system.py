import time
from pathlib import Path
from typing import Generator, NoReturn, Union, Sequence

from addon_system import Addon
from addon_system.errors import (
    AddonSystemException,
    AddonInvalid,
    AddonMetaInvalid,
    DuplicatedAddon,
)
from addon_system.libraries.base_manager import BaseLibManager
from addon_system.utils import FirstParamSingletonSingleton


class AddonSystem(metaclass=FirstParamSingletonSingleton):
    """Addon management system. Must be single instance per root"""

    def __init__(self, root: Path, lib_manager: BaseLibManager):
        if not root.is_dir():
            raise AddonSystemException("AddonSystem's root must be dir")
        self._root = root.absolute()
        self._lib_manager = lib_manager

        from addon_system.system.storage import AddonSystemStorage

        self._storage = AddonSystemStorage(self)

    @property
    def root(self):
        return self._root

    def iter_filesystem_addons(self) -> Union[Generator[Addon, None, None], NoReturn]:
        """Iter in root dir for addons"""
        from addon_system.system.storage import AddonSystemStorage

        ids: list[str] = []
        for path in self._root.iterdir():
            if path.name == AddonSystemStorage.filename:
                continue

            if not path.is_dir():
                raise AddonSystemException(f"Non-dir object in root dir. Cause: {path}")

            try:
                addon = Addon(path)
                if addon.metadata.id in ids:
                    raise DuplicatedAddon("Found multiple addons with the same id")

                self._storage.save_addon(addon)

                addon.install_system(self)

                yield addon

                ids.append(addon.metadata.id)
            except (AddonInvalid, AddonMetaInvalid) as e:
                raise AddonSystemException(
                    f"Invalid addon in root. Cause: {path}"
                ) from e

    def get_addon_by_id(self, id_: str) -> Union[Addon, None, NoReturn]:
        """Retrieves addon by its id"""
        for addon in self.iter_filesystem_addons():
            if addon.metadata.id == id_:
                return addon

    def get_addon(self, addon: str | Addon) -> Addon:
        if isinstance(addon, Addon) and not addon.path.is_relative_to(self._root):
            raise AddonInvalid(
                "Passed addon is not related to this system, this may cause some problems"
            )

        if isinstance(addon, str):
            addon_id = addon
            addon = self.get_addon_by_id(addon_id)

            if not addon:
                raise AddonInvalid(f"Addon with id {addon_id} not found")
        return addon

    def query_addons(
        self,
        author: str = None,
        name: str = None,
        description: str = None,
        enabled: bool = None,
        case_insensitivity: bool = False,
    ) -> Union[Generator[Addon, None, None], NoReturn]:
        """Used for searching addons by author, name or description"""
        for addon in self.iter_filesystem_addons():
            # Search statement
            # If any of author, name, description, enable status is matched yields addon
            if not case_insensitivity:
                string_match = (
                    (author in addon.metadata.authors)
                    or (name is not None and name in addon.metadata.name)
                    or (
                        description is not None
                        and description in addon.metadata.description
                    )
                )
            else:
                string_match = (
                    (
                        author is not None
                        and any(
                            filter(
                                lambda a: a.lower() == author, addon.metadata.authors
                            )
                        )
                    )
                    or (
                        name is not None and name.lower() in addon.metadata.name.lower()
                    )
                    or (
                        description is not None
                        and description.lower() in addon.metadata.description.lower()
                    )
                )

            if string_match or (
                enabled is not None
                and enabled == self._storage.get_addon(addon.metadata.id).enabled
            ):
                yield addon

    def set_addon_enabled(self, addon: str | Addon, enabled: bool):
        """Set value of 'enabled' for addon"""
        addon = self.get_addon(addon)

        self._storage.save_addon(addon, enabled)

    def get_addon_enabled(self, addon: str | Addon) -> bool:
        """Get value of 'enabled' of addon"""
        addon = self.get_addon(addon)

        return self._storage.get_addon(addon.metadata.id).enabled

    def enable_addon(self, addon: str | Addon):
        """Enable addon.
        This is shortcut for ::

            set_addon_enabled(addon, True)
        """
        self.set_addon_enabled(addon, True)

    def disable_addon(self, addon: str | Addon):
        """Disable addon.
        This is shortcut for ::

            set_addon_enabled(addon, False)
        """
        self.set_addon_enabled(addon, True)

    def check_dependencies(self, addon: str | Addon, use_cache: bool = True) -> bool:
        """
        Check addon dependencies

        :param addon: addon to check dependencies
        :param use_cache: use cache for retrieving result(works faster)
        """
        addon = self.get_addon(addon)

        # Use cached result. Reduces execution time
        if use_cache:
            stored_addon = self._storage.get_addon(addon.metadata.id)

            # If addon exists in cache
            # and last addon update time is earlier than last dependency check time
            # return cached result
            if (
                stored_addon
                and addon.update_time < stored_addon.last_dependency_check_time
            ):
                return stored_addon.last_dependency_check_result
            else:
                timestamp = time.time()
                result = self._lib_manager.check_dependencies(addon.metadata.depends)

                # Save dependency check result to cache
                self._storage.save_addon(addon, None, result, timestamp)

                return result

        return self._lib_manager.check_dependencies(addon.metadata.depends)

    def satisfy_dependencies(self, addon: str | Addon) -> Sequence[str]:
        """Install addon dependencies and return installed libraries"""
        addon = self.get_addon(addon)

        timestamp = time.time()
        installed = self._lib_manager.install_libraries(addon.metadata.depends)

        # Update caches
        self._storage.save_addon(
            addon, dependency_check_result=True, dependency_check_time=timestamp
        )

        return installed

    def __hash__(self):
        return hash(self._root)

    def __eq__(self, other: "AddonSystem") -> bool:
        if isinstance(other, AddonSystem):
            return self._root == other._root
        return False
