"""The patches, in the order they are applied.

A patch is a module with NAME, SUMMARY, VERSIONS (tested range), RECOMMENDED (part of the default
set), optionally CONFLICTS (patches it cannot be combined with) and REQUIRES (patches that must be
applied before it), and apply(tree, options) -> list of
report lines.  apply() raises PatchError when the code it targets is not where it expects -- it
never guesses.  See docs/writing-patches.md.
"""
from __future__ import annotations

from types import ModuleType

from . import (
               calibration,
               debug_log,
               default_palette,
               flat_field,
               fps_readout,
               full_fps,
               hidden_settings,
               http_legacy,
               lock_range,
               mic_prompt,
               no_analytics,
               no_smoothing,
               phone_camera,
               photo_1x,
               png_photos,
               reconnect_fix,
               resume_fix,
               sharp_scaling,
               shutter,
               smart_smoothing,
               smoothing_settings,
               steady_fps,
               usb_queue,
               video_quality,
)
from .base import Options

ALL: list[ModuleType] = [full_fps, steady_fps, usb_queue, default_palette, sharp_scaling, no_smoothing, smoothing_settings, png_photos,
                         hidden_settings, fps_readout, photo_1x,
                         video_quality, phone_camera, resume_fix, reconnect_fix, no_analytics, http_legacy, mic_prompt, flat_field, lock_range, shutter,
                         calibration, smart_smoothing, debug_log]
BY_NAME = {p.NAME: p for p in ALL}
RECOMMENDED = [p.NAME for p in ALL if p.RECOMMENDED]


def conflicts(names: list[str]) -> list[tuple[str, str]]:
    """The pairs among names that cannot be applied together."""
    return [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if b in getattr(BY_NAME[a], "CONFLICTS", ())]


def missing_requirements(names: list[str]) -> list[tuple[str, str]]:
    """(patch, requirement) for every patch among names whose requirement is not among them."""
    return [(a, b) for a in names for b in getattr(BY_NAME[a], "REQUIRES", ()) if b not in names]


def every_patch() -> list[str]:
    """--all: every patch, except an opt-in alternative to a patch of the default set."""
    return [p.NAME for p in ALL
            if p.RECOMMENDED or not any(c in RECOMMENDED for c in getattr(p, "CONFLICTS", ()))]


__all__ = ["ALL", "BY_NAME", "RECOMMENDED", "Options", "conflicts", "every_patch", "missing_requirements"]
