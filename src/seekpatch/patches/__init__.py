"""The patches, in the order they are applied.

A patch is a module with NAME, SUMMARY, VERSIONS (tested range), RECOMMENDED (part of the default
set) and apply(tree, options) -> list of report lines.  apply() raises PatchError when the code it
targets is not where it expects -- it never guesses.  See docs/writing-patches.md.
"""
from __future__ import annotations

from types import ModuleType

from . import (
               debug_log,
               full_fps,
               no_smoothing,
               png_photos,
               sharp_scaling,
)
from .base import Options

ALL: list[ModuleType] = [full_fps, sharp_scaling, no_smoothing, png_photos, debug_log]
BY_NAME = {p.NAME: p for p in ALL}
RECOMMENDED = [p.NAME for p in ALL if p.RECOMMENDED]

__all__ = ["ALL", "BY_NAME", "RECOMMENDED", "Options"]
