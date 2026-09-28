"""Import trusted saved project packages without an editable filesystem directory."""

import importlib.abc
import importlib.util
import sys
from types import ModuleType
from typing import Any


class _SavedSourceLoader(importlib.abc.Loader):
    """Execute one module from the immutable source attached to its model version."""

    def __init__(self, source: str, filename: str) -> None:
        self.source = source
        self.filename = filename

    def create_module(self, spec: Any) -> None:
        """Use Python's standard module construction."""
        return None

    def exec_module(self, module: ModuleType) -> None:
        """Compile the saved bytes with their diagnostic path, without reading disk."""
        module.__file__ = self.filename
        exec(compile(self.source, self.filename, "exec"), module.__dict__)  # nosec B102 - trusted model source


class _SavedPackageFinder(importlib.abc.MetaPathFinder):
    """Resolve only digest-qualified packages explicitly installed by model loading."""

    def __init__(self) -> None:
        self.packages: dict[str, dict[str, str]] = {}

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        """Leave unrelated imports to Python's normal finders."""
        root, separator, suffix = fullname.partition(".")
        files = self.packages.get(root)
        if files is None or not separator:
            return None
        stem = suffix.replace(".", "/")
        package_path = stem + "/__init__.py"
        is_package = package_path in files
        relative = package_path if is_package else stem + ".py"
        if relative not in files:
            return None
        loader = _SavedSourceLoader(files[relative], f"<{root}/{relative}>")
        return importlib.util.spec_from_loader(fullname, loader, is_package=is_package)


_FINDER = _SavedPackageFinder()


def install_project_package(name: str, files: dict[str, str]) -> None:
    """Populate a digest-specific root module and enable its relative imports.

    Called by a generated source snapshot, already verified by the model's source
    digest. Third-party imports still require installed environment dependencies.
    """
    module = sys.modules[name]
    module.__package__ = name
    module.__path__ = []
    _FINDER.packages[name] = dict(files)
    if _FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _FINDER)
    _SavedSourceLoader(files["__init__.py"], f"<{name}/__init__.py>").exec_module(module)


def discard_project_package(name: str) -> None:
    """Remove a partially imported package after a failed trusted-source load."""
    _FINDER.packages.pop(name, None)
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
