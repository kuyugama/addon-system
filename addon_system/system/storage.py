import time
from dataclasses import dataclass, asdict
from json import dump, load

from addon_system import Addon, AddonSystem
from addon_system.errors import AddonSystemException
from addon_system.utils import FirstParamSingletonSingleton


@dataclass
class StoredAddon:
    last_dependency_check_time: float
    last_dependency_check_result: bool
    enabled: bool


class AddonSystemStorage(metaclass=FirstParamSingletonSingleton):
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
        addon: Addon,
        enabled: bool = None,
        dependency_check_result: bool = None,
        dependency_check_time: float = None,
    ):
        if not isinstance(self._map.get("addons"), dict):
            self._map["addons"] = {}

        stored_addon = self.get_addon(addon.metadata.id)

        if stored_addon is not None and (
            enabled is None
            and (dependency_check_time is None and dependency_check_result is None)
            and stored_addon.last_dependency_check_time > addon.update_time
        ):
            return

        if enabled is None:
            enabled = False

        if dependency_check_time is None:
            dependency_check_time = time.time()

        if dependency_check_result is None:
            dependency_check_result = self._system.check_dependencies(addon, False)

        self._map["addons"][addon.metadata.id] = asdict(
            StoredAddon(dependency_check_time, dependency_check_result, enabled)
        )
        self.save()

    def get_addon(self, addon_id: str) -> StoredAddon | None:
        if not isinstance(self._map.get("addons"), dict):
            return None

        data = self._map["addons"].get(addon_id)

        if not data:
            return None

        return StoredAddon(**data)

    def read(self):
        if not self._path.exists():
            self.save()
            return

        with self._path.open("r", encoding="utf8") as f:
            self._map = load(f)

    def save(self):
        with self._path.open("w", encoding="utf8") as f:
            dump(self._map, f, ensure_ascii=False, indent=2)
