from typing import Generator, NoReturn, Union, Sequence
from pathlib import Path

from addon_system.addon.addon import AbstractAddon, factory as addon_factory
from addon_system.libraries.base_manager import BaseLibManager

from addon_system.errors import (
    AddonSystemException,
    AddonMetaInvalid,
    DuplicatedAddon,
    AddonInvalid,
)
from addon_system.utils import (
    string_iterable_contains,
    FirstParamSingleton,
    string_contains,
)


class AddonSystem(FirstParamSingleton):
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

    def iter_filesystem_addons(
        self,
    ) -> Union[Generator[AbstractAddon, None, None], NoReturn]:
        """Iter in root dir for addons"""
        from addon_system.system.storage import AddonSystemStorage

        ids: list[str] = []
        for path in self._root.iterdir():
            if path.name == AddonSystemStorage.filename:
                continue

            try:
                addon = addon_factory(path)

                # No addon class matched by path
                if addon is None:
                    continue

                if addon.metadata.id in ids:
                    raise DuplicatedAddon("Found multiple addons with the same id")

                self._storage.save_addon(addon)

                addon.install_system(self)

                yield addon

                ids.append(addon.metadata.id)
            except (AddonInvalid, AddonMetaInvalid) as e:
                raise AddonSystemException(f"Invalid addon in root. Cause: {path}") from e

    def get_addon_by_id(self, id_: str) -> Union[AbstractAddon, None, NoReturn]:
        """Retrieves addon by its id"""
        for addon in self.iter_filesystem_addons():
            if addon.metadata.id == id_:
                return addon

    def get_addon(self, addon: str | AbstractAddon) -> AbstractAddon:
        if isinstance(addon, AbstractAddon) and not addon.is_in_root(self):
            raise AddonInvalid(
                "Passed addon is not related to this system, " "this may cause unexpected problems"
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
    ) -> Union[Generator[AbstractAddon, None, None], NoReturn]:
        """Search for addons by author, name, description or status"""
        for addon in self.iter_filesystem_addons():
            # If author is set and this author
            # is not present in addon authors - skip addon
            if author is not None and string_iterable_contains(
                addon.metadata.authors, author, not case_insensitivity
            ):
                continue

            # If name is set and this name not in addon name - skip addon
            if name is not None and not string_contains(
                addon.metadata.name, name, not case_insensitivity
            ):
                continue

            # If description is set and this description
            # not in addon description - skip addon
            if description is not None and not string_contains(
                addon.metadata.description, description, not case_insensitivity
            ):
                continue

            # If required addon status is not equal to stored - skip addon
            if (
                enabled is not None
                and enabled != self._storage.get_stored_addon(addon.metadata.id).enabled
            ):
                continue

            yield addon

    def set_addon_enabled(self, addon: str | AbstractAddon, enabled: bool):
        """Set the status of the addon"""
        addon = self.get_addon(addon)

        self._storage.save_addon(addon, enabled)

    def get_addon_enabled(self, addon: str | AbstractAddon) -> bool:
        """Get the status of the addon"""
        addon = self.get_addon(addon)

        return self._storage.get_stored_addon(addon.metadata.id).enabled

    def enable_addon(self, addon: str | AbstractAddon):
        """
        Enable addon.
        This is a shortcut for:
        ::

            set_addon_enabled(addon, True)
        """
        self.set_addon_enabled(addon, True)

    def disable_addon(self, addon: str | AbstractAddon):
        """
        Disable addon.
        This is a shortcut for: ::

            set_addon_enabled(addon, False)
        """
        self.set_addon_enabled(addon, True)

    def check_dependencies(
        self,
        addon: str | AbstractAddon,
        use_cache: bool = True,
        force_check: bool = False,
    ) -> bool:
        """
        Check addon dependencies

        :param addon: addon to check dependencies
        :param use_cache: use cache for retrieving result(works faster)
        :param force_check: Check dependencies and write a result to cache
                (if it is set - ignores a cached result)
        """
        addon = self.get_addon(addon)

        # Use cached result. Reduces execution time
        if use_cache or force_check:
            stored_addon = self._storage.get_stored_addon(addon.metadata.id)

            # If an addon check result is cached
            # and the record is valid -> return cached result
            if (
                not force_check
                and stored_addon
                and stored_addon.last_dependency_check.is_valid(addon)
            ):
                return stored_addon.last_dependency_check.satisfied
            else:
                result = self._lib_manager.check_dependencies(addon.metadata.depends)

                # Save dependency check result to cache
                self._storage.save_addon(addon, None, result)

                return result

        return self._lib_manager.check_dependencies(addon.metadata.depends)

    def satisfy_dependencies(self, addon: str | AbstractAddon) -> Sequence[str]:
        """Install addon dependencies and return installed libraries"""
        addon = self.get_addon(addon)

        installed = self._lib_manager.install_libraries(addon.metadata.depends)

        # Update caches
        self._storage.save_addon(addon, dependency_check_result=True)

        return installed

    def __hash__(self):
        return hash(self._root)

    def __eq__(self, other: "AddonSystem") -> bool:
        if isinstance(other, AddonSystem):
            return self._root == other._root
        return False
