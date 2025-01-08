from dataclasses import dataclass, asdict, field
from json import dump, load
from hashlib import sha256
import time

from addon_system.errors import AddonSystemException
from addon_system.utils import FirstParamSingleton
from addon_system.addon.addon import AbstractAddon
from addon_system import AddonSystem


@dataclass
class DependencyCheckResult:
    satisfied: bool = False
    hash: str = field(default_factory=sha256)

    def is_valid(self, addon: AbstractAddon):
        """Check if the dependency check result is valid"""
        return addon.metadata.depends_hash == self.hash


@dataclass
class StoredAddon:
    enabled: bool
    last_dependency_check: DependencyCheckResult


class AddonSystemStorage(FirstParamSingleton):
    filename = ".as-storage.json"

    def __init__(self, system: AddonSystem):
        if not system.root.is_dir():
            raise AddonSystemException("SystemStorage root must be dir")

        self._path = system.root / AddonSystemStorage.filename
        self._system = system
        self._map = {"addons": {}, "first_init_time": time.time()}
        self.read()

    def save_addon(
        self,
        addon: AbstractAddon,
        enabled: bool = None,
        dependency_check_result: bool = None,
    ):
        if not isinstance(self._map.get("addons"), dict):
            self._map["addons"] = {}

        stored_addon = self.get_stored_addon(addon.metadata.id)

        if stored_addon is not None:
            if dependency_check_result is None:
                dependency_check_result = stored_addon.last_dependency_check.satisfied

            # Do not rewrite valid cache record
            if (
                dependency_check_result == stored_addon.last_dependency_check.satisfied
                and (enabled is None or enabled == stored_addon.enabled)
                and stored_addon.last_dependency_check.is_valid(addon)
            ):
                return

        if enabled is None:
            enabled = False

        if dependency_check_result is None:
            dependency_check_result = self._system.check_dependencies(addon, False)

        self._map["addons"][addon.metadata.id] = asdict(
            StoredAddon(  # type: ignore
                enabled,
                DependencyCheckResult(
                    dependency_check_result,
                    addon.metadata.depends_hash,
                ),
            )
        )
        self.save()

    def get_stored_addon(self, addon_id: str) -> StoredAddon | None:
        if not isinstance(self._map.get("addons"), dict):
            return None

        data = self._map["addons"].get(addon_id)

        if not data or data.get("last_dependency_check") is None:
            return None

        if data["last_dependency_check"].get("hash") is None:
            return None

        return StoredAddon(
            enabled=data.get("enabled", False),
            last_dependency_check=DependencyCheckResult(
                **data.get("last_dependency_check"),
            ),
        )

    def read(self):
        if not self._path.exists():
            self.save()
            return

        with self._path.open("r", encoding="utf8") as f:
            self._map = load(f)

    def save(self):
        with self._path.open("w", encoding="utf8") as f:
            dump(self._map, f, ensure_ascii=False, indent=2)
