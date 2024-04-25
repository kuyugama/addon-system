#! python
import argparse
from datetime import datetime
from json import dump
from pathlib import Path

from addon_system.addon import Addon

parse = argparse.ArgumentParser()

parse.add_argument("-n", "--name", help="Addon name", required=True)
parse.add_argument(
    "-a", "--authors", help='Addon authors separated by ", "', required=True
)
parse.add_argument("-i", "--id", help="Addon id", required=True)
parse.add_argument("-m", "--module", help="Addon main module", required=True)
parse.add_argument("-v", "--version", help="Addon version", default="0.0.1")
parse.add_argument("-d", "--description", help="Addon description", default="")
parse.add_argument(
    "-D", "--depends", help='Addon dependencies separated by ", "', default=None
)
parse.add_argument("-t", "--template", help="Addon module template path", default=None)
parse.add_argument("place_to", help="Path to directory in which create addon")

args = parse.parse_args()

if not Addon.validate_directory_name(args.name):
    print("Addon name must be in ascii letters and can be in CamelCase")
    exit(1)

meta = dict(
    name=args.name,
    authors=args.authors.replace(", ", ",").split(","),
    id=args.id,
    module=args.module[:-3] if args.module.endswith(".py") else args.module,
    version=args.version,
    description=args.description,
    depends=(
        args.depends.replace(", ", ",").split(",") if args.depends is not None else []
    ),
)

addon_path = Path(args.place_to) / args.name

if addon_path.exists():
    print("Addon already exists")
    exit(2)

addon_path.mkdir()

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
    id=args.id,
    datetime=datetime.now(),
)

module_path = addon_path / args.module
if not args.module.endswith(".py"):
    module_path = addon_path / (args.module + ".py")

with module_path.open("w", encoding="utf8") as f:
    f.write(module)

meta_path = addon_path / "addon.json"

with meta_path.open("w", encoding="utf8") as f:
    dump(meta, f, ensure_ascii=False, indent=2)
