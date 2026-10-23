"""What every patch shares: its options and the marker that makes re-applying it an error."""
from __future__ import annotations

from dataclasses import dataclass

from ..smali import AlreadyApplied, SmaliTree


@dataclass(frozen=True)
class Options:
    sharpness: float = 2.0
    """sharp_scaling: texels blend over 1/sharpness of their width (1 = stock bilinear, 2 = iOS)."""
    video_codec: str = "hevc"
    """video_quality: "hevc" or "avc" (H.264), the codec tried first."""
    video_qp: int = 18
    """video_quality: constant quantizer (lower = better and bigger)."""


def mark(name: str) -> str:
    """The comment a patch leaves on every line it adds."""
    return f"# seek-patch {name}"


def ensure_unpatched(tree: SmaliTree, name: str) -> None:
    if tree.containing(mark(name)):
        raise AlreadyApplied(f"{name}: already applied")
