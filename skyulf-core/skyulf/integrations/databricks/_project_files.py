"""Capture bounded project source and locate hooks in legacy or organized layouts."""

import keyword
from pathlib import Path

from ...inference.project_code import MAX_PROJECT_SOURCE_BYTES, project_source_digest


def read_source(path: Path) -> str:
    """Read a bounded UTF-8 source file without truncating the saved program."""
    with path.open("rb") as stream:
        payload = stream.read(MAX_PROJECT_SOURCE_BYTES + 1)
    if len(payload) > MAX_PROJECT_SOURCE_BYTES:
        raise ValueError(f"{path.name} source exceeds 64 KiB.")
    return payload.decode("utf-8")


def _module_path(path: Path, root: Path) -> str:
    """Reject escaping paths and filenames that cannot be imported unambiguously."""
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Project package source must stay inside its root.")
    relative = path.relative_to(root)
    for name in (*relative.parts[:-1], relative.stem):
        if not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError(f"Project Python module needs an importable name: {relative}.")
    return relative.as_posix()


def _validate_package_files(files: dict[str, str]) -> None:
    """Require explicit package boundaries and reject module/package name collisions."""
    if "__init__.py" not in files:
        raise ValueError("Project package must contain __init__.py.")
    for filename in files:
        for parent in Path(filename).parents:
            if (parent / "__init__.py").as_posix() not in files:
                raise ValueError(f"Project package needs {parent}/__init__.py.")
        if (
            filename.endswith("/__init__.py")
            and filename.removesuffix("/__init__.py") + ".py" in files
        ):
            raise ValueError(f"Project module conflicts with its package: {filename}.")


def project_source(path: Path) -> str:
    """Keep single-file snapshots compatible or archive a complete Python package."""
    if not path.is_dir():
        return read_source(path)
    files = {}
    size = 0
    for filename in sorted(path.rglob("*.py"), key=lambda item: item.relative_to(path).as_posix()):
        relative = _module_path(filename, path)
        source = read_source(filename)
        size += len(source.encode("utf-8"))
        if size > MAX_PROJECT_SOURCE_BYTES:
            raise ValueError("Project package source exceeds 64 KiB.")
        files[relative] = source
    _validate_package_files(files)
    source = (
        "from skyulf.inference.project_package import install_project_package\n"
        f"install_project_package(__name__, {files!r})\n"
    )
    project_source_digest(source)
    return source


def modeling_hook(path: Path, name: str) -> Path:
    """Resolve organized feature packages beside modeling, or legacy sibling hooks."""
    return path.parent / "modeling" / name if path.is_dir() else path.with_name(name)
