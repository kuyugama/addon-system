from collections.abc import Sequence
from typing import Any
import warnings
import inspect
import typing
import types
import sys

from addon_system.libraries.base_manager import BaseLibManager
from addon_system.utils import deprecated
from addon_system import utils
from ..errors import AddonSystemException

if typing.TYPE_CHECKING:
    from .addon import AbstractAddon

# Contains all modules used by all addons
# In a format: module instance => list of addons that uses this module
_modules: dict[types.ModuleType, list] = {}


def unload_module(module: types.ModuleType):
    """Removes module and its children from ``sys.modules`` if it is present"""
    for name in tuple(sys.modules.keys()):
        if name.startswith(module.__name__):
            del sys.modules[name]


class ModuleInterface:
    """
    Used to implement module interface

    Always calls ``on_load`` (if exists) method on class instance initiation.
    If on_load returns list of modules used by addon - when tries to unload module,
    also unloads used modules

    Can fully unload module(if it is the only usage of the addon's module).
    This will not work always, but it can try :3

    Example: ::

        from pathlib import Path
        import logging

        from addon_system import ModuleInterface, Addon


        class MyInterface(ModuleInterface):
            def ping(self):
                '''Calls ping module function and returns True, if not exists returns False'''
                func = self._get_func("ping")
                if not func:
                    return False

                func()

                return True

        addon = Addon(Path("addons/SomeAddon"))

        # Replace name "this" in addon module
        addon.module(replace_names=dict(this=addon))

        # Immediately calls on_load if it exists
        interface = addon.interface(cls=MyInterface)

        if interface.ping():
            logging.getLogger("AddonLoader").debug(f"Successfully called ping function in addon {addon.metadata.id}")

        # In this case - module will be fully unloaded from memory
        interface.unload()
    """

    def __init__(self, addon: "AbstractAddon", lib_manager: BaseLibManager):
        called_from = inspect.stack()[1]
        from addon_system.addon.addon import AbstractAddon

        if not isinstance(addon, AbstractAddon):
            raise TypeError(f"Invalid addon type provided: {type(addon)}")

        # Check caller
        if (
            called_from.filename != inspect.getfile(AbstractAddon)
            and called_from.function != "interface"
        ):
            raise RuntimeError("Can be created only from addon interface() method")

        # Reason for lib_manager to be "public" is to allow(haha, can i forbid?) developers to change it
        self.lib_manager = lib_manager

        self._addon = addon
        self._module = None

        self._used_modules: list[types.ModuleType] = []

    @property
    def module_loaded(self) -> bool:
        return self._module is not None

    def _module_or_raise(self):
        if not self.module_loaded:
            raise RuntimeError(
                "Module is not loaded! "
                f"Load module with interface.load()"
            )

        return self._module

    def get_func(self, name: str) -> types.FunctionType | None:
        """
        Gets function from the module, returns None if not present,
        or name is not a valid variable name in python
        """
        if not name.isidentifier():
            return

        func = getattr(self._module_or_raise(), name, None)

        if not isinstance(func, types.FunctionType):
            return

        return func

    def set_attrs(self, **names):
        """
        Installs provided attributes to module
        """
        for name, value in names.items():
            setattr(self._module_or_raise(), name, value)

    def get_attr(self, name: str, **kw) -> Any:
        """
        Gets attribute from module and raises AttributeError if attribute not exists in module

        if default is provided - returns default instead of raising AttributeError
        :param name: Attribute name
        :returns: Value of attribute
        """
        has_default = "default" in kw

        if not hasattr(self._module_or_raise(), name) and not has_default:
            raise AttributeError(name)

        return getattr(self._module_or_raise(), name, kw.get("default"))

    @deprecated("Use get_attr instead", "1.2.0")
    def _get_attr(self, name: str, **kw) -> Any:
        return self.get_attr(name, **kw)

    @deprecated("Use set_attrs instead", "1.2.0")
    def _set_attrs(self, **names):
        return self.set_attrs(**names)

    @deprecated("Use get_func instead", "1.2.0")
    def _get_func(self, name: str):
        return self.get_func(name)

    def load(self, *args: Any, **kwargs: Any):
        """
        Loads module and calls on_load callback
        """
        if self.module_loaded:
            raise AddonSystemException("Module already loaded")

        self._module = self._addon.module(self.lib_manager)

        callback = self.get_func("on_load")

        if callback is None:
            return self

        modules = callback(*args, **kwargs)

        if not isinstance(modules, Sequence):
            return self

        for module in modules:
            if not inspect.ismodule(module):
                continue

            addons = _modules.setdefault(module, [])
            if self._addon not in addons:
                addons.append(self._addon)

            self._used_modules.append(module)

        return self

    def unload(self, *args, **kwargs):
        """
        Tries to unload module

        Raises RuntimeError if module has
        more than 4 refs(addon instance, this instance, ``sys.modules``, addons root module).

        All arguments will be passed to on_unload module method
        """

        ref_count = sys.getrefcount(self._module_or_raise()) - 1

        if ref_count > 4:
            raise RuntimeError("Cannot unload: more than 4 refs to module found")

        handler = self.get_func("on_unload")

        if handler is not None:
            handler(*args, **kwargs)

        if ref_count == 4:
            addons_root = self._addon.path.parent
            import_path = utils.get_module_import_path(addons_root)
            if import_path in sys.modules:
                addons_root_module = sys.modules[import_path]

                if hasattr(addons_root_module, self._addon.path.name):
                    delattr(addons_root_module, self._addon.path.name)

        # Remove reference from addon instance
        self._addon._module = None

        unload_module(self._module)

        self._module = None

        # Unload module if it is used only in this addon
        for module in tuple(self._used_modules):
            self._used_modules.remove(module)

            addons = _modules.get(module, [])

            if len(addons) < 2:
                unload_module(module)
                del _modules[module]
                continue

            addons.remove(self._addon)

    def __del__(self):
        # If instance created with error - _module attribute will not be present
        if not hasattr(self, "_module"):
            return

        if self._module is not None:
            try:
                self.unload()
            except RuntimeError as e:
                warnings.warn(e.args[0])
