from pathlib import Path


class AddonSystemException(BaseException):
    """Something went wrong. Base class of all exceptions that raises AddonSystem or its components"""

    def __init__(self, message: str):
        self.args = (message,)


class BuildError(AddonSystemException):
    """Something went wrong in building the addon"""


class BuildOrderError(AddonSystemException):
    """The build order is violated"""


class AddonMetaInvalid(AddonSystemException):
    """Addon metadata is invalid"""

    def __init__(self, message: str, path: Path):
        self.message = message
        self.path = path

    def __str__(self):
        return "{message} <==> Meta path: {path}".format(path=self.path, message=self.message)


class AddonInvalid(AddonSystemException):
    """Cannot create addon wrapper at current path"""

    pass


class AddonImportError(AddonInvalid):
    """Addon import error. If dependency check fails it will be raised"""

    pass


class DuplicatedAddon(AddonInvalid):
    """Addon id duplicates found"""

    pass
