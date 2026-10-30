"""flat_field: a "Flat field" button that removes the gradient of an unevenly warmed camera.

libseekip's gradient stage (filter bit 0x80, on in both "Image smoothing" positions) subtracts a
smooth correction map and learns that map only from frames that already look flat: no 16x16 block
with more detail than feature 30100, no step between neighbouring blocks beyond 30102.  The map
starts empty on every connect, and a camera that has warmed unevenly puts its own gradient into
every frame, so after a warm restart it never learns.  Feature 30105 makes the stage learn from
every frame regardless; neither the app nor the library ever sets it.

The patch adds:
    a button in the camera screen's top bar      seekpatch.Flat.attach, after setContentView
    a call right after the per-frame feature 900  seekpatch.Flat.frame(handle): on a tap it sets
                                                  30105 until the update counter (30104) has gone
                                                  up by 40 -- the map moves 1/8 per frame -- then
                                                  clears it
    seekpatch.SeekIP                              the app's seekIPsetFeature / seekIPgetFeature
                                                  (shared with smoothing_settings, see seek.py)
    the "Flat field frames" setting               seekpatch.FlatSettings, in Settings -> Image &
                                                  Video (settings.py): 5 - 60 frames a tap, 40 by
                                                  default

Versions: the gradient features are verified in libseekip 2.10.5.0 (app 2.2.2) and 2.11.3.2
(2.2.3 - 2.3.4); the patch keeps to the apps smoothing_settings is verified on.  Source of the helper:
helpers/java/seekpatch/Flat.java; see docs/flat-field.md.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import PatchError, SmaliTree, class_descriptor
from .base import ensure_unpatched, mark
from .seek import camera_activity, feature_900_call, seekip_class
from .settings import optional_settings

NAME = "flat_field"
SUMMARY = 'a "Flat field" button: point at a uniform surface, tap, and the camera\'s own gradient is removed'
VERSIONS = "2.2.0 - 2.3.4"
MIN_VERSION_CODE = 260  # 2.2.0
RECOMMENDED = True

MARK = mark(NAME)

def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version, and the patch is only verified on {VERSIONS}")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) predates the image "
                         f"libraries whose gradient stage the patch is verified on (apps {VERSIONS})")
    call = feature_900_call(tree, NAME)
    setfeature, getfeature = seekip_class(tree, NAME)
    activity_path, after_layout = camera_activity(tree, NAME)
    activity = class_descriptor(tree.get(activity_path))

    text = tree.get(call.path)
    hook = (f"\n{call.indent}{MARK}: the Flat field button's request, before the frame is processed\n"
            f"{call.indent}invoke-static {{p1, p2}}, Lseekpatch/Flat;->frame(J)V\n")
    tree.set(call.path, text[:call.end] + hook + text[call.end:])

    text = tree.get(activity_path)
    indent = re.match(r"[ \t]*", text[text.rfind("\n", 0, after_layout - 1) + 1:]).group(0)
    hook = (f"\n{indent}{MARK}: the Flat field button, in the top bar\n"
            f"{indent}invoke-static {{p0}}, Lseekpatch/Flat;->attach(Landroid/app/Activity;)V\n")
    tree.set(activity_path, text[:after_layout] + hook + text[after_layout:])

    add_helpers(tree, "Flat", "TopBar")
    return [f"{tree.rel(call.path)}: Flat.frame after the feature-900 call; features via {setfeature} / {getfeature}",
            f"{tree.rel(activity_path)}: the button after {activity.split('/')[-1][:-1]}.setContentView",
            *optional_settings(tree, NAME, "FlatSettings", "Flat field frames")]
