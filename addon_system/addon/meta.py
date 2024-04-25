from json import load, dump
from pathlib import Path
from typing import Any

from addon_system.errors import AddonMetaInvalid

DEFAULTS = dict(version="0.0.1", description="", depends=[])

field_types = dict(
    id=str,
    module=str,
    depends=list,
    name=str,
    description=str,
    authors=list,
    version=str,
)


class AddonMeta:
    id: str
    module: str
    depends: list[str]
    name: str
    description: str
    authors: list[str]
    version: str

    def __init__(self, path: Path):
        if not path.exists():
            raise AddonMetaInvalid("Addon meta doesn't exists", path)

        if not path.name == "addon.json":
            raise AddonMetaInvalid('Addon meta file\'s name must be "addon.json"', path)

        self._path = path
        self._data = {}
        self.read()

    def _required_fields(self, required_fields: list[str], content: dict[str, Any]):
        for field in required_fields:
            if field not in content:
                raise AddonMetaInvalid(
                    f"Metadata file content must include {field} field", self._path
                )

    def _fields_types(self, content: dict[str, Any]):
        for field_name, field_type in field_types.items():
            value = content.get(field_name)

            if value is None:
                continue

            if not isinstance(value, field_type):
                raise AddonMetaInvalid(
                    f'Field "{field_name}" has invalid type {type(value).__name__}. '
                    f"Required type is {field_type.__name__}",
                    self._path,
                )

            if field_name in ("depends", "authors"):
                if any(filter(lambda e: not isinstance(e, str), value)):
                    raise AddonMetaInvalid(
                        f'All elements of the "{field_name}" field must be strings.',
                        self._path,
                    )

    def _validate_content(self, content: dict[str, Any]):
        self._required_fields(["id", "module", "name", "authors"], content)
        self._fields_types(content)

    def _install_defaults(self, content: dict[str, Any]):
        save = False
        for key, value in DEFAULTS.items():
            if key not in content:
                save = True
                content[key] = value

        if save:
            with self._path.open("w", encoding="utf8") as f:
                dump(content, f, ensure_ascii=False, indent=2)

    def read(self):
        """Reads the content of metadata file"""
        with self._path.open("r", encoding="utf8") as f:
            content = load(f)
            if not isinstance(content, dict):
                raise AddonMetaInvalid(
                    f"Addon meta file contains invalid data type: {type(content).__name__}",
                    self._path,
                )

            self._validate_content(content)
            self._install_defaults(content)

            self._data = content

    def __getattr__(self, item):
        if item not in self._data:
            raise AttributeError(f"Metadata doesn't have {item} field")

        return self._data[item]

    __getitem__ = __getattr__

    def __str__(self):
        return (
            f"AddonMeta<{self.id}>"
            f"(name={self.name!r}, "
            f"version={self.version!r}, "
            f"path={str(self._path.absolute())!r})"
        )
