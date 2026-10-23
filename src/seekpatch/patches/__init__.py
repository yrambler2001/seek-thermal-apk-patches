"""The patches, in the order they are applied.

A patch is a module with NAME, SUMMARY, VERSIONS (tested range), RECOMMENDED (part of the default
set) and apply(tree, options) -> list of report lines.  apply() raises PatchError when the code it
targets is not where it expects -- it never guesses.  See docs/writing-patches.md.
"""
from __future__ import annotations

from types import ModuleType

from . import (
               debug_log,
               flat_field,
               full_fps,
               mic_prompt,
               no_smoothing,
               photo_1x,
               png_photos,
               resume_fix,
               sharp_scaling,
               video_quality,
)
from .base import Options

ALL: list[ModuleType] = [full_fps, sharp_scaling, no_smoothing, png_photos, photo_1x, video_quality, resume_fix,
                         mic_prompt, flat_field, debug_log]
BY_NAME = {p.NAME: p for p in ALL}
RECOMMENDED = [p.NAME for p in ALL if p.RECOMMENDED]

__all__ = ["ALL", "BY_NAME", "RECOMMENDED", "Options"]
