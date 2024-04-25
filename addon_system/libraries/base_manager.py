from abc import ABC, abstractmethod
from typing import Sequence


class BaseLibManager(ABC):
    """Library management class. Must be single instance per project"""

    instance: "BaseLibManager"

    def __new__(cls):
        if hasattr(cls, "instance"):
            return cls.instance

        cls.instance = super().__new__(cls)

        return cls.instance

    @abstractmethod
    def check_dependencies(self, dependencies: list[str]) -> bool:
        """
        Checks if the dependencies of addon is satisfied
        :param dependencies: dependency list. Format is name==version
        """
        raise NotImplementedError

    @abstractmethod
    def get_installed_libraries(self, force: bool = False) -> dict[str, str]:
        """
        Used to get installed libraries.
        For example using **pip freeze**

        Please, cache the libraries if this takes more than 1 second per call\

        :param force: Used to force retrieve libraries
        """
        raise NotImplementedError

    @abstractmethod
    def install_libraries(self, libraries: Sequence[str]) -> Sequence[str]:
        """
        Install passed libraries

        :param libraries: Libraries to install. Format: name==version
        """
        raise NotImplementedError
