from dataclasses import dataclass
from types import ModuleType
from typing import Union
from pathlib import Path
import inspect
import json

from addon_system.errors import BuildOrderError, BuildError
from addon_system import AddonSystem

__all__ = ["StringModule", "AddonPackageBuilder", "AddonBuilder"]


try:
    import pybaked

except ImportError:
    pybaked = None


@dataclass
class StringModule:
    code: str
    name: str

    def __post_init__(self):
        if not self.name.endswith(".py"):
            self.name += ".py"

        if not self.code.endswith("\n"):
            self.code += "\n"

    @property
    def stem(self):
        return self.name[:-3]


class AddonPackageBuilder:
    """
    PackageBuilder class is responsible for building addon packages

    Example:
    ::

        builder = AddonPackageBuilder.from_path("/path/to/python-package")
        builder.set_main("main_module_name.py")
        builder.build("/path/to/addon-directory")
    """

    def __init__(self, name: str = "."):
        self.main = None
        self.name = name
        self._modules: list[StringModule] = []
        self._children: list[AddonPackageBuilder] = []

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "AddonPackageBuilder":
        """
        Make AddonPackageBuilder from a path

        Includes all child packages

        Sets __init__.py as main module if present

        :return: AddonPackageBuilder
        """
        if isinstance(path, str):
            path = Path(path)

        if not path.exists() or not path.is_dir():
            raise ValueError("Invalid package path")

        builder = AddonPackageBuilder(path.name)

        for subpath in path.iterdir():
            if subpath.name == "__pycache__":
                continue

            if subpath.is_dir():
                builder.add(AddonPackageBuilder.from_path(subpath))

            if subpath.is_file() and subpath.suffix == ".py":
                builder.add(StringModule(subpath.read_text(encoding="utf-8"), subpath.name))

                # If there are __init__.py it may be main module of this package
                if subpath.name == "__init__.py":
                    builder.set_main(subpath.name)

        return builder

    def add(self, module: Union[StringModule, ModuleType, "AddonPackageBuilder"]):
        """
        Add module or child package to addon package
        """

        if isinstance(module, ModuleType):
            module = StringModule(inspect.getsource(module), module.__name__)

        if isinstance(module, StringModule):
            if "." in module.stem and self.name != module.stem.split(".")[-1]:
                self.add(
                    AddonPackageBuilder(module.stem.split(".", 1)[0]).add(
                        StringModule(module.code, module.stem.split(".", 1)[1])
                    )
                )

                return self

        if isinstance(module, StringModule):
            if self.exists(module):
                raise ValueError("Module already exists")

            self._modules.append(module)

            if module.name == "__init__.py" and not self.main:
                self.set_main(module.name)

        elif isinstance(module, AddonPackageBuilder):
            self._children.append(module)
        else:
            raise TypeError("Invalid module type")

        return self

    def exists(self, name: str | ModuleType | StringModule) -> bool:
        if isinstance(name, ModuleType):
            name = name.__name__ + ".py"

        elif isinstance(name, StringModule):
            name = name.name

        else:
            if not name.endswith(".py"):
                name += ".py"

        for module in self._modules:
            if (
                isinstance(module, StringModule)
                and module.name == name
                or isinstance(module, ModuleType)
                and module.__name__ == name
            ):
                return True

        return False

    def set_main(self, name: str):
        """
        Set the main module for this package (used to build addon metadata)
        """
        if not name.endswith(".py"):
            name += ".py"

        if not self.exists(name):
            raise ValueError("Module not found")

        self.main = name

        return self

    def to_dict(self) -> dict[str, str]:
        """Unpacks all packages into a python dict"""
        content: dict[str, str] = {}

        for module in self._modules:
            content[module.stem] = module.code

        for child in self._children:
            for module, code in child.to_dict().items():
                content[child.name + "." + module] = code

        return content

    def build(self, package_root: Union[str, Path], unpack: bool = False):
        """Builds package from given modules and child packages

        :param package_root: Where to build package
        :param unpack: If set - will not create subdirectory for this package
        """
        if isinstance(package_root, str):
            package_root = Path(package_root)

        if not unpack:
            package_root = package_root / self.name

        if package_root.exists() and not package_root.is_dir():
            raise ValueError("Invalid package path")

        package_root.mkdir(parents=True, exist_ok=True)

        for module in self._modules:
            with open(package_root / module.name, "w", encoding="utf8") as mf:
                mf.write(module.code)

        for child in self._children:
            child.build(package_root)


class AddonBuilder:
    """
    AddonBuilder class is responsible for creating addons from the code

    Example:
    ::

        builder = AddonBuilder()
        builder.meta(
            name="AddonName",
            authors=["First author", "Second author"],
            version="1.0.0",
            depends=["aiogram==*"],
            id="FirstAuthor/AddonName",
            description="Addon description"
        )
        builder.package(AddonPackageBuilder().add(StringModule()))
        builder.save("/path/to/root")
    """

    def __init__(self):
        self._package: AddonPackageBuilder | None = None
        self._meta = {}

    def package(self, package: AddonPackageBuilder):
        """
        Set the module to the addon that will be created

        If module is string - module_name must be passed
        """

        self._package = package

        return self

    def meta(
        self,
        name: str,
        authors: list[str],
        version: str = "0.0.1",
        depends: list[str] = None,
        id: str = None,
        description: str = "",
    ):
        """
        Set the metadata for the addon that will be created
        """

        if depends is None:
            depends = []

        if id is None:
            id = authors[0] + "/" + name

        self._meta.update(
            dict(
                name=name,
                authors=authors,
                version=version,
                depends=depends,
                id=id,
                description=description,
            )
        )

        return self

    def _build_default(self, at: Path) -> Path:
        at.mkdir()

        meta = self._meta
        meta.update(dict(module=self._package.main))

        with (at / "addon.json").open("w", encoding="utf8") as metafile:
            json.dump(meta, metafile, indent=2, ensure_ascii=False)

        self._package.build(at, unpack=True)

        return at

    def _build_baked(self, at: Path) -> Path:
        meta = self._meta
        meta.update(dict(module=self._package.main))

        baker = pybaked.BakedMaker(True, meta)

        for module_name, source in self._package.to_dict().items():
            baker.include_module(module_name.encode(), source.encode())

        return baker.file(at)

    def build(
        self,
        path: str | Path | AddonSystem,
        addon_dir_name: str = None,
        baked: bool = False,
    ) -> Path:
        """
        Builds the addon at the given path

        :param path: Where to build addon.
                if AddonSystem given - will make addon path using its root
                and addon name stored to metadata
        :param addon_dir_name: Where to build addon.
                This allows change default behavior if the AddonSystem passed
                as path(will take this name instead of name stored in metadata)
        :param baked: If True - will make "baked" addon
                using "pybaked" library, but if it is not installed will
                raise ValueError

        :return: Path to built addon
        """
        if not self._meta:
            raise BuildOrderError("No meta set")

        if not self._package:
            raise BuildOrderError("No package set")

        if self._package.main is None:
            raise BuildError("Provided package does not have a main module")

        if isinstance(path, AddonSystem):
            root = path.root

            path = root / self._meta["name"]
            if addon_dir_name is not None:
                path = root / addon_dir_name

            if path.exists():
                raise BuildError(
                    "This path already exists. Try to choose another addon name or pass another addon_dir_name"
                )

        elif isinstance(path, str):
            path = Path(path)

        if not baked:
            return self._build_default(path)

        else:
            if pybaked is None:
                raise ValueError('Cannot build "baked" addon: pybaked is not installed')

            return self._build_baked(path)
