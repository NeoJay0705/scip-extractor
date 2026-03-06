from __future__ import annotations

from pathlib import Path

from scip_deep_context.models import PathResolverError


def resolve_entry_file(project_root: str, entry_file: str) -> str:
    """Convert *entry_file* to a path relative to *project_root*.

    Raises PathResolverError when the file does not exist or is outside
    the project root.
    """
    root = Path(project_root).resolve()
    entry = Path(entry_file)

    if entry.is_absolute():
        resolved = entry.resolve()
    else:
        resolved = (root / entry).resolve()

    if not resolved.exists():
        raise PathResolverError(f"Entry file does not exist: {resolved}")

    try:
        rel = resolved.relative_to(root)
    except ValueError:
        raise PathResolverError(
            f"Entry file {resolved} is outside project root {root}"
        )

    return str(rel)


def normalize_uri(uri: str, project_root: str) -> str:
    """Normalize a URI to a relative path under *project_root*."""
    root = Path(project_root).resolve()
    p = Path(uri)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(root))
        except ValueError:
            return uri
    return str(Path(uri))


def is_within_project(uri: str, project_root: str) -> bool:
    """Return True if *uri* refers to a location inside *project_root*."""
    root = Path(project_root).resolve()
    p = Path(uri)
    if p.is_absolute():
        try:
            p.resolve().relative_to(root)
            return True
        except ValueError:
            return False
    # Relative paths are assumed to be within the project
    resolved = (root / p).resolve()
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False
