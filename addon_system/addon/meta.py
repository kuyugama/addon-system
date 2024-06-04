from typing import Any, TypeVar
from json import load, dump
from pathlib import Path
import os.path
import copy
import json
import time

from addon_system.errors import AddonMetaInvalid
from addon_system import utils

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


class AddonMetaExtra:
    """
    Addon metafile extra info representation(Mutable).

    Addon metafile extra info is a custom user data that can be changed in code.
    This data can be read without importing addon module.

    You may subclass it to provide your typehints.

    **Note**: Class will **not** validate data from file by
    set type-hints. You need to write own ``validate`` implementation

    Example: ::

        class Extra(AddonMetaExtra):
            # Will be set if field is not present in extra info
            __defaults__ = {"handles_events": []}
            handles_events: list[str]


        extra = addon.metadata.extra(Extra)

        if "smth" in extra.handles_events:
            print("Addon", addon.metadata.id, "can handle \"smth\" event")
    """

    # Defaults that will be set if not present in extra
    __defaults__: dict[str, Any] = {}

    def __init__(self, data: dict[str, Any], meta: "AddonMeta"):
        self._metadata = meta
        self._data = data

        for key, value in self.__defaults__.items():
            if key in data:
                continue
            data[key] = value

        if not self.validate(data):
            raise AddonMetaInvalid(
                "Invalid extra data provided in metafile", meta.path
            )

    @property
    def metadata(self) -> "AddonMeta":
        return self._metadata

    def validate(self, data: dict[str, Any]) -> bool:  # noqa
        """
        Validates extra input data. Validators can change incoming data by modifying provided ``dict`` to it.

        May return False if invalid, or raise an AddonMetaInvalid exception
        """
        return True

    def save(self):
        """Saves extra data changes to metafile"""
        self._metadata.save()

    def get(self, key: str, default: Any = None):
        """Returns value of a given extra field name. If it is not exists - returns **default** value"""
        if not self.has(key):
            return default

        return self._data[key]

    def setdefault(self, key: str, default: Any = None):
        """Return value of a field or sets the default and return it"""
        if not self.has(key):
            self[key] = default

        return self._data[key]

    def has(self, key: str):
        return key in self._data

    __contains__ = has

    def __getattr__(self, item):
        """Return value of a field if it exists, else - raise AttributeError"""
        if not self.has(item):
            raise AttributeError(f"Extra doesn't have {item} field")

        return self._data[item]

    __getitem__ = __getattr__

    def __setattr__(self, key: str, value: Any):
        """Validates and sets the value to metadata extra"""
        if key.startswith("_"):
            super().__setattr__(key, value)
            return

        type_invalid = TypeError(
            f"Cannot set value of type {type(value)}. "
            f"Is not JSON serializable or invalid."
        )

        try:
            json.dumps(value)
            new_data = self._data | {key: value}
            if not self.validate(new_data):
                raise type_invalid
        except (TypeError, AddonMetaInvalid) as e:
            raise type_invalid from e

        self._data.update(new_data)

    __setitem__ = __setattr__

    def __delattr__(self, item):
        """Remove field if it exists, else - raise AttributeError"""
        if not self.has(item):
            raise AttributeError(f"Extra doesn't have {item} field")

        del self._data[item]

    __delitem__ = __delattr__

    def __str__(self):
        return f"AddonMetaExtra[{self.metadata.path}]({json.dumps(self._data, ensure_ascii=False)})"


E = TypeVar("E", bound=AddonMetaExtra)


class AddonMeta:
    """Addon metafile representation(Immutable)"""

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
            raise AddonMetaInvalid(
                'Addon meta file\'s name must be "addon.json"', path
            )

        self._path = path
        self._data = {}

        self._read_time = None

        self.read()
    
    @property
    def depends_hash(self) -> str:
        return utils.hash_string_tuple(tuple(self.depends))

    @property
    def path(self) -> Path:
        return self._path

    @property
    def update_time(self) -> float:
        """Addon metafile update time"""
        return os.path.getmtime(self._path)

    def _required_fields(
        self, required_fields: list[str], content: dict[str, Any]
    ):
        """Checks if all required fields are set"""
        for field in required_fields:
            if field not in content:
                raise AddonMetaInvalid(
                    f"Metadata file content must include {field} field",
                    self._path,
                )

    def _fields_types(self, content: dict[str, Any]):
        """Checks types of fields in metafile content"""
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
        """Validates content of metafile"""
        self._required_fields(["id", "module", "name", "authors"], content)
        self._fields_types(content)

    @staticmethod
    def _install_defaults(content: dict[str, Any]):
        """Sets default values to optional fields and returns True if at least one is set"""
        defaults_installed = False
        for key, value in DEFAULTS.items():
            if key not in content:
                defaults_installed = True
                content[key] = value

        return defaults_installed

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
            defaults_installed = self._install_defaults(content)

            self._data = content

            if defaults_installed:
                self.save()

        self._read_time = time.time()

    def save(self):
        """
        Saves changes of the metadata into a file.

        **Note**: only extra in metadata is mutable
        """
        with self._path.open("w", encoding="utf8") as f:
            dump(self._data, f, ensure_ascii=False, indent=2)

        self._read_time = time.time()

    def extra(self, cls: type[E] = AddonMetaExtra) -> E:
        """Creates proxy for extra data in metafile"""

        if not issubclass(cls, AddonMetaExtra):
            raise TypeError(
                f"Cannot create AddonMetaExtraProxy from type {type(cls)}"
            )

        data = self._data.setdefault("extra", {})

        return cls(data, self)

    def __getattr__(self, item):
        if item not in self._data:
            raise AttributeError(f"Metadata doesn't have {item} field")

        if item not in field_types:
            raise ValueError(
                f"Cannot get {item} - use AddonMeta.extra to get/set custom values"
            )

        # If metafile is updated - read changes and then get the value
        if self.update_time > self._read_time:
            self.read()

        value = self._data[item]

        if isinstance(value, (dict, list)):
            value = copy.copy(value)

        return value

    __getitem__ = __getattr__

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return (
            f"AddonMeta<{self.id}>"
            f"(name={self.name!r}, "
            f"version={self.version!r}, "
            f"path={str(self._path.absolute())!r})"
        )
