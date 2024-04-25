import subprocess
import sys
from pathlib import Path
from typing import cast, Sequence

from addon_system.libraries.base_manager import BaseLibManager

NOT_EXACT_VERSION_ERROR = ValueError(
    "PipLibManager supports only exact version installs for now. Example: urllib3==1.25.8"
)


class PipLibManager(BaseLibManager):
    def __init__(self):
        self._pip_executable = Path(sys.executable).parent / "pip"

        self._installed_libraries = None

    def check_dependencies(self, dependencies: list[str]) -> bool:
        libraries = self.get_installed_libraries()
        for dep in dependencies:
            if "==" not in dep:
                raise NOT_EXACT_VERSION_ERROR

            name, version = dep.split("==")

            if libraries.get(name) != version:
                return False

        return True

    def install_libraries(self, libraries: Sequence[str]) -> tuple[str]:
        libraries: list[str] = list(libraries)

        if self._installed_libraries is None:
            self.get_installed_libraries()

        # Check validness of input names and drop already installed libraries(if exists)
        for lib in libraries.copy():
            if "==" not in lib:
                raise NOT_EXACT_VERSION_ERROR

            name, version = lib.split("==")

            if self._installed_libraries.get(name) == version:
                libraries.remove(lib)

        if len(libraries):
            out = subprocess.getoutput(
                str(self._pip_executable.absolute()) + " install " + " ".join(libraries)
            )
            if "ERROR" in out:
                raise RuntimeError("Error occurred while installing: {}".format(out))

        # Save installed libraries
        for name in libraries:
            name, version = name.split("==")

            self._installed_libraries[name] = version

        return cast(tuple[str], libraries)

    def get_installed_libraries(self, force: bool = False) -> dict[str, str]:
        """
        **Gets from the pip the installed libraries**

        :param force: Force read from pip
        :return: dictionary of libraries {library_name: version}
        """

        if force or self._installed_libraries is None:
            pip_out = subprocess.getoutput(
                str(self._pip_executable.absolute()) + " freeze"
            )

            libs = {}

            for lib_line in pip_out.splitlines():
                lib = lib_line.lower().split("==")

                if len(lib) < 2:
                    continue

                name, version = lib
                libs[name] = version

            self._installed_libraries = libs

        return self._installed_libraries
