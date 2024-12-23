import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path

from addon_system.addon.builder import (
    AddonBuilder,
    AddonPackageBuilder,
    StringModule,
)
from addon_system.addon import Addon
from addon_system.errors import AddonSystemException

parse = argparse.ArgumentParser()

parse.add_argument("-n", "--name", help="Addon name", required=True)
parse.add_argument(
    "-a",
    "--authors",
    help='Addon authors separated by ", "',
    required=True,
)
parse.add_argument("-m", "--module", help="Addon main module", default=None)
parse.add_argument("-p", "--package", help="Path to source code package", default=None)
parse.add_argument("-i", "--id", help="Addon id", default=None)
parse.add_argument("-v", "--version", help="Addon version", default="0.0.1")
parse.add_argument("-d", "--description", help="Addon description", default="")
parse.add_argument("-D", "--depends", help='Addon dependencies separated by ", "', default=None)
parse.add_argument("-t", "--template", help="Addon module template path", default=None)
parse.add_argument(
    "-f",
    "--force",
    help="Overwrite existing addon",
    default=False,
    action="store_true",
)
parse.add_argument(
    "-b",
    "--bake",
    help="Bake addon to a single file. Requires pybaked to be installed. "
    "Recommended to use with -p parameter",
    default=False,
    action="store_true",
)
parse.add_argument(
    "--no-color",
    help="forces tool to not use color",
    default=False,
    action="store_true",
)
parse.add_argument("place_to", help="Path to directory in which create addon", default=".")

USE_COLORS = True


def color(s: str, code: int) -> str:
    if not USE_COLORS:
        return str(s)

    s = str(s)

    if "\x1b[0m" in s:
        s = s.replace("\033[0m", f"\033[{code}m")

    return f"\033[{code}m{s}\033[0m"


def red(s: str) -> str:
    return color(s, 31)


def green(s: str) -> str:
    return color(s, 32)


def yellow(s: str) -> str:
    return color(s, 33)


def cyan(s: str) -> str:
    return color(s, 36)


def print_error(s: str) -> None:
    print(red(s))


def main() -> int:
    args = parse.parse_args()

    try:
        import pybaked
    except ImportError:
        if args.bake:
            print(
                red(
                    f"{yellow('pybaked')} is not installed "
                    f"({cyan('caused by -b / --bake parameter')})"
                )
            )
            return 6

    if args.no_color:
        global USE_COLORS
        USE_COLORS = False

    builder = AddonBuilder()

    if not Addon.validate_name(args.name):
        print_error("Addon name must be in ascii letters and can be in CamelCase")
        return 1

    authors = args.authors.replace(", ", ",").split(",")

    id_ = args.id

    if not id_:
        id_ = authors[0] + "/" + args.name

    builder.meta(
        name=args.name,
        authors=authors,
        id=id_,
        version=args.version,
        description=args.description,
        depends=(args.depends.replace(", ", ",").split(",") if args.depends is not None else []),
    )

    root_dir = Path(args.place_to)

    if not root_dir.exists():
        root_dir.mkdir()

    if not root_dir.is_dir():
        print_error("place_to parameter must be a path to a directory")
        return 4

    addon_path = root_dir / args.name

    if addon_path.exists() and not args.force:
        try:
            Addon(addon_path)
            print_error("Addon already exists")
            return 2
        except AddonSystemException:
            print_error("Non-addon object is at this path")
            return 3

    if args.template:
        with open(args.template, "r", encoding="utf8") as f:
            module = f.read()
    else:
        module = """"""

    module = module.format(
        name=args.name,
        authors=args.authors,
        version=args.version,
        description=args.description,
        id=id_,
        datetime=datetime.now(),
    )

    if args.package:
        print(f"Using {green(args.package)} as source package")
        package = AddonPackageBuilder.from_path(args.package)
        builder.package(package)

        if args.module:
            try:
                package.set_main(args.module)
            except ValueError:
                print_error(f"{cyan(args.module)} not found in source package")
                return 5

        if not package.main:
            print_error("No main module found in source package")
            return 5

        print(f"Using {green(package.main)} as main module")
    elif args.module:
        print(f"Using {green(args.module)} as main module")
        builder.package(
            AddonPackageBuilder().add(StringModule(module, args.module)).set_main(args.module)
        )
    else:
        print(f"Using {green('__init__.py')} as main module")
        builder.package(AddonPackageBuilder().add(StringModule(module, "__init__")))

    if args.force and addon_path.exists():
        if addon_path.is_dir():
            shutil.rmtree(addon_path)
        else:
            os.remove(addon_path)

    addon_path = str(builder.build(addon_path, baked=args.bake))

    print(f"Successfully created addon {green(args.name)}[{yellow(id_)}] at {cyan(addon_path)}")

    return 0


if __name__ == "__main__":
    exit(main())
