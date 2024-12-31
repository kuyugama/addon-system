# # _Addon System_

> This is a fully rewritten RelativeAddonsSystem
> [\[PyPi\]](https://pypi.org/project/relative-addons-system)
> [\[GitHub\]](https://github.com/KuyuGama/RelativeAddonsSystem)

## What is it?

> This is super useful (or useless. Depends on your mood) thing ever!

This is a library that allows you
to manage "addons" in your project.

> You want to install only one library?
> **Just do it!**
>
>It has no third-party dependencies!

## What is addon?

> Beneficial thing!

Addon is a mini-project(usually independent)
that provides an interface for your main project
and can be used as a part of it.

Addon is a directory that contains at least two files:

- Addon metafile
- Addon main module

### Addon metafile

Is a JSON formatted file. That consists of these values:

- id - `string`. Addons must have unique id. Usually
  consists of your username and addon name: `KuyuGama/SomeAddon`
- name - `string`. Name of addon.
  Can be used for frontend display
- module - `string`. Main module of addon
- authors - `array[string]`. Author names
  of addon
- version - [optional] `string`. Version of addon(usually SemVer)
- description - [optional]`string`. Description of addon.
  Can be used on frontend
- depends - [optional]`array[string]`. Addon dependencies. Format is library==version
  (such as pip). If you are using your own
  library managing class, you can change
  a string format to yours.
- extra - [optional]`object`. Addon extra info. Used to store custom values that can be changed in runtime.

### Addon module

Is a standard python module!
The only exception is an interface that will use your main code of project.

> I've been inspired by a plugins
> for Minecraft servers cores such as a
> [Paper](https://papermc.io) to create this library!

## What is addon for?

> Speed or convenience? I choose both!

Addon is a runtime extension of your project.
You can write update for your application
and don't care about downtime
(it will not be there!).

Or you can use addons just for creating
extensible projects. For example, telegram bots,
you can add some functionality with
no need to edit the main code of the bot. 
Connect the addon!

## Dependencies?

> Where is aiogram gone?

This library has a built-in tool for
managing addon's dependencies.
So you don't even need to use
command-line to install it using AddonSystem.

## Let's try?

> LET'S GOO!

### Prerequisites

- Install `addon-system`

```bash
pip install addon-system
```

- Create addons storage directory, it can have any name and be anywhere inside your project workdir(of course!)

Example:

```
┌─ KuyuGenesis -- Workdir
└──┌─ addons -- here you go
   ├─ src
   ├─ main.py
   ├─ config.py
   └─ KuyuGenesis.conf
```

### Create your first addon

There are two ways to achieve it

- Using library-provided addon creation
  command line tool:

```bash
make-addon -name "SomeAddon" -a "KuyuGama,KugaYumo" -i "KuguYama/SomeAddon" -m __init__ addons
```

- Manually(meh) create addon dir and metafile:

```
┌─ SomeAddon -- AddonDir (CamelCase)
└──┌─ addon.json -- metafile
   └─ __init__.py -- module set in metafile(can be any python file)
```

So you now have this project structure:

```
┌─ KuyuGenesis -- Workdir
└──┌─ addons 
   ├──┌─ SomeAddon -- Addon's directory
   │  └─┌─ addon.json -- metafile
   │    └─ __init__.py -- module set in metafile
   ├─ src
   ├─ main.py
   ├─ config.py
   └─ KuyuGenesis.conf
```

### Initialize the system

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())
```

Here we created instance of the AddonSystem
with early created addons root directory
and `pip` library manager.
If you use another library manging tool -
 write your own implementation of
library manager that uses it (only three methods!).

### Querying addons

> Search of addons? YES!

For your needs, you can search for the addons(not on the internet! Yet?)

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

for addon in system.query_addons(name="some", case_insensitivity=True):
    print(addon)
```

Here we queried for addon by its name case-insensitive.
You can query addons by other fields also.
Here are all query parameters:

- author — author name
- name — addon name
- description — description
- enabled — addon status(about this later)
- case_insensitivity — case-insensitive querying

### Getting a specific addon

As I wrote above:
> Addon's must have unique id

So, if you want to get some exact addon - use its id!

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")
print(addon)
```

### Addon details

> What is the use of this addon?

You can get all supported values from metafile using 
AddonMeta that is always present in addon as "metadata" attribute:
```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")
metadata = addon.metadata
print(metadata.id)
print(metadata.name)
print(metadata.description)
print(metadata.version)
print(metadata.depends)
print(metadata.authors)
print(metadata.module)
```

Addon metafile has one more field "extra." 
Which can be used to store custom values:

```python
from typing import Any
from pathlib import Path

from addon_system import AddonSystem, AddonMetaExtra
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")


class Extra(AddonMetaExtra):
    __defaults__ = {"handles_events": []}
    handles_events: list[str]
    priority: int

    def validate(self, data: dict[str, Any]) -> bool:
        handles_events = data.get("handles_events")
        if not isinstance(handles_events, list):
            return False
        
        # If not all elements are str -> return False
        if isinstance(handles_events, list) and (
            len(handles_events) != 0
            and all(map(lambda e: isinstance(e, str), handles_events))
        ):
            return False

        return True


extra = addon.metadata.extra(Extra)

if "event" in extra.handles_events:
    print(f"{addon.metadata.id} can handle event \"event\"")
    # Set priority extra value and save metafile
    extra.priority = 0
    extra.save()
```

> Note: you can read/edit addon extra info without the need to 
> create your own AddonMetaExtra class subclass.
> But it is useful when you have to define types of field or validate 
> data from extra info

### Dependencies!

To manage dependencies, you have to use the simple
interface:

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")

print(addon.metadata.depends)
print("Is dependencies satisfied?", system.check_dependencies(addon))
if not system.check_dependencies(addon):
    system.satisfy_dependencies(addon)
    print("Auto-installed dependencies")
...
```

Here we checked dependencies of addon and installed it if necessarily

> `check_dependencies` and `satisfy_dependencies`
> also can take addon id to manage
>
> Thanks to caching we can call `check_dependencies`
> twice without losing much time

### Addon status

> Another useful (or useless, according to your purposes) think!

Addon status allows the code to know whether to
load addon into your project

Usage:

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")

if not system.get_addon_enabled(addon):
    system.enable_addon("KuyuGama/SomeAddon")
else:
    system.disable_addon("KuyuGama/SomeAddon")

for addon in system.query_addons(enabled=True):
    print("Enabled addon:", addon)
```

> To remove confusion:
>
> `get_addon_enabled`, `enable_addon` and `disable_addon` all
> can take id or instance of addon

### Importing addon

> Much more interesting, isn't it?

You can import or reload module of addon
where and when you want:

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")

module = addon.module()

# Example module interface
event_handlers = {}

module.unpack_handlers(event_handlers)
```

> Note, addon can't be imported without satisfied dependencies.
> If dependencies are not satisfied, exception will be raised

> Interface of addon module is your own designed
> interface for your purposes.
>
> Because the module is a regular python module, you can  
> create whatever you want

Reload of module is achieved by using the same function with `reload=True` argument:

```python
from pathlib import Path

from addon_system import AddonSystem
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")

module = addon.module(reload=True)
```

### Value injection

Value injection is way to pass some values into addon before it is loaded

There are two ways to inject values into addon:
1. Builtin injection (deprecated)
2. Namespace usage

## Builtin injection
This type of value injection sets the values into ``builtins`` so the values can be 
accessed on addon module loading. But this way is not thread safe, because what is set 
to ``builtins`` is can be accessed not only in module that is loading now, but from anywhere 
and that may create problems in your program or libraries you use.

But, if you sure in what you doing here is the example:

```python
from pathlib import Path

from addon_system import Addon
from addon_system.libraries.pip_manager import PipLibManager

addon = Addon(Path("path/to/addon"))
addon.namespace.name = "value"

addon.module(PipLibManager(), builtin_injection=True)

# In addon module:
print(name)
```

As you see - IDEs will cry about that way of injecting values. Also, this is magical and hard 
to understand why you're trying to access name that does not exist.

> Also, this type of injection work only on main module that is set in addon.json file

## Namespace usage
This type of value injection uses the special object AddonNamespace that stores 
all passed values into addon. Values passed through this way can be accessed in all addon's modules.

Here is the example:
```python 
from pathlib import Path

from addon_system import Addon
from addon_system.libraries.pip_manager import PipLibManager

addon = Addon(Path("path/to/addon"))
addon.namespace.name = "value"

addon.module(PipLibManager())

# In addon module:
from addon_system import AddonNamespace

namespace = AddonNamespace.use()

name = namespace.get("name", str)
# IDEs will say that "name" variable is of str type

print(name)
print(namespace.name)  # this is also possible
```

### Module Interface

> Wait, what? My IDE now suggests to me methods that I could call!

How this works: you create class-representation of the module -
library instantiates it with addon and allows you to use it anywhere.

Simple example:

```python
from pathlib import Path
from typing import Any

from addon_system import AddonSystem, ModuleInterface
from addon_system.libraries.pip_manager import PipLibManager


class MyInterface(ModuleInterface):
    def get_supported_events(self) -> list[str]:
        """Returns supported events by this addon"""
        return self.get_func("get_supported_events")()

    def propagate_event(self, event_name: str,
                        event_data: dict[str, Any]) -> bool:
        """Propagates event to this addon, and return True if handled"""
        handler = self.get_func("on_" + event_name)

        if handler is None:
            return False

        return handler(event_data)


root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")

# Value injection can be achieved by using addon.namespace dictionary
addon.namespace.update(this=addon)

interface = addon.interface(MyInterface)

# load module and call on_load callback function inside this module
interface.load(
    "supported on_load positional argument",
    kwd="supported on_load keyword argument"
)

if "smth" in interface.get_supported_events():
    interface.propagate_event("smth", dict(issued_by="User"))
```

> ModuleInterface class has built-in methods to manipulate on addon's module:
> 
> `get_func(name: str)` — returns function with the given name, if it is not a function — returns None
> 
> `get_attr(name: str[, default=Any])` — get attribute by the given name, if default is not set - raises AttributeError
> 
> `set_attrs(**names)` — set passed keyword arguments as module attributes

### Module unloading

> Free my memory, please

Library can try to unload addon's modules

> **Note**: It works better in a pair of ModuleInterface

```python
from pathlib import Path

from addon_system import AddonSystem, ModuleInterface
from addon_system.libraries.pip_manager import PipLibManager

root = Path() / "addons"
system = AddonSystem(root, PipLibManager())

addon = system.get_addon_by_id("KuyuGama/SomeAddon")

module = addon.module()

# To unload module => we must remove all references to it
# (and then python's garbage collector will release used memory by it)
del module
addon.unload_module()

# In case of usage ModuleInterface, it will try to unload 
# all used modules by this addon(addon's module must return 
# a list of the modules in on_load method)
interface = addon.interface(ModuleInterface).load()

# Will try to unload all used modules by its addon
interface.unload("Argument passed to on_unload module method")
## Or
# addon.unload_interface("Argument passed to on_unload module method")
## if you don't have access to interface instance
```

> **NOTE**!!! Unload may not work in case if module is used anywhere else.
> If you use interface - use it instance instead of the addon's module
>
> Also: to unload used modules by this addon => you need to
> return a list of these modules from on_load module method
> (it will be called automatically by ``ModuleInterface`` class)
> 
> I recommend not using addon's module object, instead use ModuleInterface. 
> That is a good idea, because it will unload module if necessary 

--------------------------------

## Addon creation tool

> It is easy to create addon!

Library provides tools to create addons via terminal and code:

### Command-line addon building
`make-addon` is designed to create addons easily using terminal

Parameters:  
-n / --name — Addon name(must be CamelCase because tool creates addon directory with the same name)  
-a / --authors — Comma separated author names  
-i / --id — Addon id (If not provided will be created using **first author name** + **"/"** + **addon name**)  
-m / --module — Set the main module name of this addon (Useful when creating from source code)  
-p / --package — Path to package that will be used as addon source  
-v / --version — Version of addon (Usually SemVer)  
-d / --description — Description of addon  
-D / --depends — Comma separated addon dependencies (in `pip freeze` format)  
-t / --template — Path to module template file (Will be used if no source package is provided)  
-f / --force — Force create addon (rewrites addon if exists)  
-b / --bake — Build "baked" addon using ``pybaked`` library. I Recommend
use it in pair with --package parameter   
place_to — Directory where addon will be created  


### In-code addon building
`addon_system.addon.builder.AddonBuilder` and `addon_system.addon.builder.AddonPackageBuilder` 
are designed to build addons from code easily

#### `addon_system.addon.builder.AddonBuilder`

Methods:
- `meta(name: str, authors: list[str], version: str, depends: list[str], id: str, description: str)`  
    Sets the metadata of this addon
- `package(package: AddonPackageBuilder)`  
    Sets the package of this addon
- `build(path: str | Path | AddonSystem, addon_dir_name: str = None)`  
    Builds addon at given path. If the path is AddonSystem object then addon_dir_name must be passed (addon's root)


#### `addon_system.addon.builder.AddonPackageBuilder`

Methods:
- [classmethod] `from_path(path: str | Path)`  
    Create AddonPackageBuilder instance from path. Includes all modules and child packages within given path
- `add(module: StringModule | ModuleType | AddonPackageBuilder)`  
    Add module or sub package to this package
- `build(path: str | Path, unpack: bool = False)`  
    Build this package at given path  
    If `unpack` set to `True` - will source of this package at root of given path 
    (Useful if instance is created using `from_path`)

Example of building addon from code:

```python
from addon_system.addon.builder import AddonBuilder, AddonPackageBuilder, StringModule

package = AddonPackageBuilder.from_path("addon-source")
package.add(StringModule("print(1, 2, 3)", "__init__"))
package.set_main("__init__")

builder = AddonBuilder()
builder.meta(
    name="AddonName",
    authors=["KuyuGama"],
    version="0.0.1",
    depends=["pyyaml==6.0.1"],
    id="KuyuGama/AddonName",
    description="Addon description"
)
builder.package(package)
builder.build("addons/AddonName")
```


--------------------------------

## Addon interface

> Independent addon? Huh

Addons are semi-independent components of AddonSystem.

This means you can use addons without AddonSystem(but with some limitations, of course)

Here are the all methods and properties of semi-independent component Addon:

1. Properties:
    - `metadata` — Metadata class contains all the metadata of addon
    - `path` — Path to addon
    - `update_time` — last update time of addon(retrieved from an operating system)
    - `module_path` — path to addon's module
    - `namespace` — custom namespace of all addon's modules (you may need 
            to edit that to pass desired values on module initialization)
    - `module_import_path` — path that passed into `importlib.import_module` to import module of addon
    - `system` — installed AddonSystem for this addon(not for independent usage)
    - `enabled` — addon status shortcut(not for independent usage)
2. Methods:
    - `install_system(system: AddonSystem)`
        - system — AddonSystem to install

      Install AddonSystem to this addon(usually used by AddonSystem)
    - `module(lib_manager: BaseLibManager = None, reload: bool = False)`
        - lib_manager — Library manager, used to check
          dependencies before import of module.
          You must pass it if you use addon as an independent object
        - reload — Pass True if you want to reload module(uses `importlib.reload`)

      Import the Addon module
    - `interface(cls: type[ModuleInterface] = ModuleInterface, lib_manager: BaseLibManager = None)`
        - cls — subclass of ModuleInterface that will be instantiated
        - lib_manager — Library manager, used to check
          dependencies before import of module.
          You must pass it if you use addon as an independent object

      Create ModuleInterface instance that can be used to access module
      variables with IDEs suggestions
      > Note: from version 1.2.19 ModuleInterface does not load module on instantiating. For loading module - call ModuleInterface.load(*args, **kwargs) method that will load module and call ``on_load`` callback  
    - `unload_interface()`
        - *args, **kwargs — will be passed to ``on_unload`` method of the addon

      Tries to unload module interface

    - `unload_module()`

      Tries to unload module

    - `storage()`

      Get the addon key-value storage.
      Use it if your addon has data to store

    - `check_dependencies(lib_manager: BaseLibManager = None)`
        - lib_manager — Library manager, used to check
          dependencies before import of module.
          You must pass it if you use addon as an independent object

      Check addon dependencies
    - `satisfy_dependencies(lib_manager: BaseLibManager = None)`
        - lib_manager — Library manage, used to install libraries.
          You must pass it if you use the addon as an independent component

      Install dependencies of this addon
    - `set_enabled(enabled: bool)`
        - enabled — status of addon

      Get the addon status (not for independent usage)
    - `enable()`  
      Enable addon(not for independent usage)
    - `disable()`  
      Disable addon(not for independent usage)
    - `bake_to_bytes()`  
      "Bake" this addon to bytes using `pybaked` library. Returns bytes
    - `bake_to_file()`  
      "Bake" this addon to file using `pybaked` library. 
      Returns path to created file

# Thanks for using!
