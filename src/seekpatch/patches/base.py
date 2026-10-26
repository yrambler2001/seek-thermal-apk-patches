"""What every patch shares: the marker that makes re-applying it an error."""
from __future__ import annotations

from .. import LEGACY_NAME
from .. import NAME as PROJECT
from ..smali import AlreadyApplied, SmaliTree


def mark(name: str) -> str:
    """The comment a patch leaves on every line it adds."""
    return f"# {PROJECT} {name}"


def ensure_unpatched(tree: SmaliTree, name: str) -> None:
    if tree.containing(mark(name)) or tree.containing(f"# {LEGACY_NAME} {name}"):  # or patched before 1.0
        raise AlreadyApplied(f"{name}: already applied")
