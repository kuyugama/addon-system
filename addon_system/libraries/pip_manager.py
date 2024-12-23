from typing import cast, Sequence, Callable, Any, Iterable
from packaging.version import Version
from pathlib import Path
import subprocess
import operator
import sys

from addon_system.libraries.base_manager import BaseLibManager

__all__ = ["PipLibManager"]

OPERATORS: dict[str, Callable] = {
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "!=": operator.ne,
    "~=": lambda x, y: x >= y and x.release[0] == y.release[0],
}


def split_dependency(dependency: str) -> tuple[str, str]:
    """
    Split dependency to name and clause

    :param dependency: Dependency to split
    :return: Tuple of name and clause
    """
    for index, char in enumerate(dependency):
        if char in "><=!~":
            return dependency[:index], dependency[index:]

    raise ValueError(f"Invalid dependency {dependency}: Not found version specification")


def find_operators(
    clauses: Iterable[str],
) -> list[tuple[Callable[[Any, Any], bool], Version]]:
    """
    Find operators to compare with for version clauses

    :param clauses: iterable of version clauses (example: [">=2.0.1", "<=2.1.1"])
    :return: list of tuples of operators and related versions
        (example:
            [(operator.ge, Version("2.0.1")), (operator.le, Version("2.1.1"))])
    """
    operators: list[tuple[Callable[[Any, Any], bool], Version]] = []

    for clause in clauses:
        for index, char in enumerate(clause):
            # Catch < and > operators
            if char in "><" and clause[index + 1] != "=":
                operators.append(
                    (
                        OPERATORS[char],
                        Version(clause[index + 1 :].strip()),
                    )
                )
                break

            # Catch other operators
            operators.append(
                (
                    OPERATORS[char + clause[index + 1]],
                    Version(clause[index + 2 :].strip()),
                )
            )
            break

    return operators


class DependencyComparison:
    def __init__(self, dependency: str):
        name, clause = split_dependency(dependency)
        self.name: str = name.strip()

        self.clauses: list[tuple[Callable[[Any, Any], bool], Version]] = find_operators(
            map(lambda c: c.strip(), clause.split(","))
        )

    def is_compatible(self, version: str | Version) -> bool:
        if not isinstance(version, Version):
            version = Version(version)

        for clause_operator, clause_version in self.clauses:
            if not clause_operator(version, clause_version):
                return False

        return True


class PipLibManager(BaseLibManager):
    def __init__(self):
        self._pip_executable = Path(sys.executable).parent / "pip"

        self._installed_libraries = None

    def check_dependencies(self, dependencies: list[str]) -> bool:
        libraries = self.get_installed_libraries()
        for dep in dependencies:
            comp = DependencyComparison(dep)

            if comp.name not in libraries:
                return False

            if not comp.is_compatible(libraries.get(comp.name)):
                return False

        return True

    def install_libraries(self, libraries: Sequence[str]) -> tuple[str]:
        libraries: list[str] = list(libraries)

        if self._installed_libraries is None:
            self.get_installed_libraries()

        # Check validness of input names and drop already installed libraries(if exists)
        for lib in libraries.copy():
            comp = DependencyComparison(lib)

            if comp.name not in self._installed_libraries:
                continue

            if comp.is_compatible(self._installed_libraries.get(comp.name)):
                libraries.remove(lib)

        if len(libraries):
            out = subprocess.getoutput(
                str(self._pip_executable) + " install " + " ".join(f'"{lib}"' for lib in libraries)
            )
            if "ERROR" in out:
                raise RuntimeError("Error occurred while installing: {}".format(out))

        # Drop installed libraries cache
        self._installed_libraries = None

        return cast(tuple[str], libraries)

    def get_installed_libraries(self, force: bool = False) -> dict[str, str]:
        """
        **Gets from the pip the installed libraries**

        :param force: Force read from pip
        :return: dictionary of libraries {library_name: version}
        """

        if force or self._installed_libraries is None:
            pip_out = subprocess.getoutput(str(self._pip_executable.absolute()) + " freeze")

            libs = {}

            for lib_line in pip_out.splitlines():
                lib = lib_line.lower().split("==")

                if len(lib) < 2:
                    continue

                name, version = lib
                libs[name] = version

            self._installed_libraries = libs

        return self._installed_libraries
