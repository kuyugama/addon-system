import inspect
import typing

from addon_system import utils

if typing.TYPE_CHECKING:
    from .addon import AbstractAddon


T = typing.TypeVar("T")
DefType = type[T]
RetType = T


class AddonNamespace(utils.FirstParamSingleton):
    """
    The addon namespace utility class.
    Stores values that can be accessed within addon. Can be used to pass some program values to addon that cannot be imported.

    Usage:
    ::
        # In program
        addon.namespace.name = "value"
        addon.namespace.update(set="multiple", values="at, once="")

        # In addon
        from addon_system import AddonNamespace

        namespace = AddonNamespace.use()
        print(namespace.value)

        var = namespace.get("name", int)
        # IDEs will see "var" as int type
    """

    def __init__(self, addon: "AbstractAddon"):
        self._addon = addon

        self._values = {}

    @classmethod
    def use(cls: DefType) -> RetType:
        """
        Use current addon's namespace.
        """
        addon = utils.find_addon(inspect.stack()[1].filename)

        if addon is None:
            raise RuntimeError("AddonNamespace can be used only in addons")

        return cls(addon)

    def empty(self) -> bool:
        return len(self._values) == 0

    def get(self, name: str, _: DefType = typing.Any) -> RetType:
        if name not in self._values:
            raise KeyError(name)

        return self._values[name]

    def set(self, name: str, value: typing.Any) -> None:
        self._values[name] = value

    def update(self, modifier: typing.Mapping[str, typing.Any] = None, **values) -> None:
        if modifier is None:
            modifier = {}
        self._values.update(modifier, **values)

    def pop(self, name: str, _: DefType = typing.Any) -> RetType:
        return self._values.pop(name, None)

    def raw(self) -> dict[str, typing.Any]:
        return self._values

    def items(self) -> typing.ItemsView[str, typing.Any]:
        return self._values.items()

    def keys(self) -> typing.KeysView[str]:
        return self._values.keys()

    def values(self) -> typing.ValuesView[typing.Any]:
        return self._values.values()

    def __getattr__(self, item):
        try:
            return self.get(item)
        except KeyError:
            pass

        raise AttributeError(item)

    __getitem__ = get

    __delitem__ = __delattr__ = pop

    def __str__(self):
        name = self.__class__.__qualname__
        return f"{name}<{self._addon.metadata.id}>({self._values.__repr__()})"

    def __repr__(self):
        return self.__str__()
