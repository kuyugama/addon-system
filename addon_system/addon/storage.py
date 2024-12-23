import json
from typing import Any

from .addon import Addon


class AddonStorage:

    def __init__(self, addon: Addon):
        self._path = addon.path / "storage.json"

        self._map = {}

        self.read()

    def exists(self):
        return self._path.exists()

    def initialize(self, default_data: dict):
        if not isinstance(default_data, dict):
            raise ValueError("Default data should be dictionary type")

        flush = False

        for key, value in default_data.items():
            if key not in self._map:
                self._map[key] = value
                flush = True

        if flush:
            self.save()

    def read(self):
        if not self.exists():
            self._map = {}
            return

        with self._path.open("r", encoding="utf8") as file:
            self._map = json.load(file)

    def save(self):
        with self._path.open("w", encoding="utf8") as file:
            json.dump(self._map, file, ensure_ascii=False, indent=2)

    def get(self, name: str, default: Any = None) -> int | str | dict | list | float | bool:
        if name not in self._map:
            return default
        return self._map[name]

    def set(self, name: str, value: int | str | dict | list | float | bool):
        json.dumps(value)

        self._map[name] = value

    def remove(self, name: str):
        if name not in self._map:
            raise KeyError(name)

        del self._map[name]

    def keys(self):
        return self._map.keys()

    def __setitem__(self, key, value):
        self.set(key, value)

    def __getitem__(self, item):
        if item not in self._map:
            raise KeyError(item)

        return self._map[item]

    def __delitem__(self, item):
        self.remove(item)

    def __contains__(self, item):
        return item in self._map

    has = __contains__
