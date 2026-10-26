"""The patches, in the order they are applied.

A patch is a module with NAME, SUMMARY, VERSIONS (tested range), RECOMMENDED (part of the default
set), optionally REQUIRES (patches that must be applied before it), and apply(tree) -> list of
report lines.  apply() raises PatchError when the code it targets is not where it expects -- it
never guesses.  See docs/writing-patches.md.
"""
from __future__ import annotations

from types import ModuleType

from . import (
               calibration,
               debug_log,
               default_palette,
               default_unit,
               flat_field,
               fps_readout,
               full_fps,
               hidden_settings,
               http_legacy,
               lock_range,
               mic_prompt,
               no_analytics,
               phone_camera,
               photo_1x,
               png_photos,
               reconnect_fix,
               relaunch_fix,
               resume_fix,
               sharp_scaling,
               shutter,
               smart_smoothing,
               smoothing_settings,
               steady_fps,
               usb_prompt,
               video_quality,
)

ALL: list[ModuleType] = [full_fps, steady_fps, default_palette, default_unit, sharp_scaling, smoothing_settings, png_photos,
                         hidden_settings, fps_readout, photo_1x,
                         video_quality, phone_camera, resume_fix, reconnect_fix, usb_prompt, relaunch_fix, no_analytics, http_legacy, mic_prompt, flat_field, lock_range, shutter,
                         calibration, smart_smoothing, debug_log]
BY_NAME = {p.NAME: p for p in ALL}
RECOMMENDED = [p.NAME for p in ALL if p.RECOMMENDED]


def missing_requirements(names: list[str]) -> list[tuple[str, str]]:
    """(patch, requirement) for every patch among names whose requirement is not among them."""
    return [(a, b) for a in names for b in getattr(BY_NAME[a], "REQUIRES", ()) if b not in names]


def every_patch() -> list[str]:
    """--all: every patch."""
    return [p.NAME for p in ALL]


__all__ = ["ALL", "BY_NAME", "RECOMMENDED", "every_patch", "missing_requirements"]
