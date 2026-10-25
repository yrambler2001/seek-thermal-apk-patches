"""The patches, in the order they are applied.

A patch is a module with NAME, SUMMARY, VERSIONS (tested range), RECOMMENDED (part of the default
set), optionally CONFLICTS (patches it cannot be combined with), and apply(tree, options) -> list of
report lines.  apply() raises PatchError when the code it targets is not where it expects -- it
never guesses.  See docs/writing-patches.md.
"""
from __future__ import annotations

from types import ModuleType

from . import (
               debug_log,
               default_palette,
               flat_field,
               full_fps,
               lock_range,
               mic_prompt,
               no_smoothing,
               photo_1x,
               png_photos,
               resume_fix,
               sharp_scaling,
               smart_smoothing,
               smoothing_settings,
               video_quality,
)
from .base import Options

ALL: list[ModuleType] = [full_fps, default_palette, sharp_scaling, no_smoothing, smoothing_settings, png_photos, photo_1x,
                         video_quality, resume_fix, mic_prompt, flat_field, lock_range, smart_smoothing, debug_log]
BY_NAME = {p.NAME: p for p in ALL}
RECOMMENDED = [p.NAME for p in ALL if p.RECOMMENDED]


def conflicts(names: list[str]) -> list[tuple[str, str]]:
    """The pairs among names that cannot be applied together."""
    return [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if b in getattr(BY_NAME[a], "CONFLICTS", ())]


def every_patch() -> list[str]:
    """--all: every patch, except an opt-in alternative to a patch of the default set."""
    return [p.NAME for p in ALL
            if p.RECOMMENDED or not any(c in RECOMMENDED for c in getattr(p, "CONFLICTS", ()))]


__all__ = ["ALL", "BY_NAME", "RECOMMENDED", "Options", "conflicts", "every_patch"]
