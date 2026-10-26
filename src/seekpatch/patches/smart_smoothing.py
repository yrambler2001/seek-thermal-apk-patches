"""smart_smoothing: a "Smart smoothing" button that swaps the app's temporal smoothing for a
motion-compensated noise filter.

The app's temporal filter (libseekip's alpf, first-filter bit 0x4) only blends pixels that did not
change, so a hand-held camera gets almost nothing from it, or smear.  seek-thermal-apk-patches' filter (written
for this project, helpers/native/tnr.c) aligns each frame to a running estimate -- frame-wide shift
and level, then per 16 px tile -- and averages up to 8 frames per pixel, dropping pixels that do not
match (motion the alignment missed).  It also removes column stripes (lines = 3) and levels the
strip at the screen's left edge (edge = 6): the research build's "NR new+LE".

The patch adds:
    lib/<abi>/libseekpatch_smooth.so             the filter, and a hook that points libseekip's GOT
                                                  entries for filter_process / filter_process_shutter
                                                  at wrappers: the first filter runs without alpf, and
                                                  its output is filtered in place, so temperatures,
                                                  photos and video get the cleaner frame
    a button in the camera screen's top bar      seekpatch.Smooth.attach, after setContentView
    a call right after the per-frame feature 900  seekpatch.Smooth.frame(): loads and hooks on the
                                                  first switch on, then passes the switch on

Off (the default; the choice is kept in the app's preferences) is the stock app: the library is
not loaded until the button is first switched on, and after that the wrappers only forward.

Versions: libseekip calls the two functions through its PLT from 2.2.3 on (libseekip 2.11.3.2);
2.2.0 - 2.2.2's library calls them directly, so there is nothing to hook.  At run time the hook
also checks the library is one of the four builds it was verified on (arm64-v8a and armeabi-v7a
of 2.2.3 - 2.3.0 and of 2.3.1 - 2.3.4) and otherwise turns itself off.  Built for arm64-v8a and
armeabi-v7a only.  Sources: helpers/native, helpers/java/seekpatch/Smooth.java; see
docs/smart-smoothing.md.
"""
from __future__ import annotations

import re

from .. import native
from ..helpers import add_helpers
from ..smali import PatchError, SmaliTree, class_descriptor
from .base import ensure_unpatched, mark
from .seek import camera_activity, feature_900_call

NAME = "smart_smoothing"
SUMMARY = 'a "Smart smoothing" button: a motion-compensated noise filter instead of the app\'s temporal smoothing'
VERSIONS = "2.2.3 - 2.3.4"
MIN_VERSION_CODE = 276  # 2.2.3
RECOMMENDED = True

MARK = mark(NAME)
SEEKIP = "libseekip.so"


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version, and the patch is only verified on {VERSIONS}")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) predates the image "
                         f"library the hook is verified on (apps {VERSIONS})")
    abis = [a for a in tree.abis if a in native.ABIS and tree.has_native(a, SEEKIP)]
    if not abis:
        raise PatchError(f"{NAME}: no {SEEKIP} for {' / '.join(native.ABIS)} in the apk "
                         f"(it has native code for: {', '.join(tree.abis) or 'none'})")
    call = feature_900_call(tree, NAME)
    activity_path, after_layout = camera_activity(tree, NAME)
    activity = class_descriptor(tree.get(activity_path))

    text = tree.get(call.path)
    hook = (f"\n{call.indent}{MARK}: switch the noise filter on / off, before the frame is processed\n"
            f"{call.indent}invoke-static {{}}, Lseekpatch/Smooth;->frame()V\n")
    tree.set(call.path, text[:call.end] + hook + text[call.end:])

    text = tree.get(activity_path)
    indent = re.match(r"[ \t]*", text[text.rfind("\n", 0, after_layout - 1) + 1:]).group(0)
    hook = (f"\n{indent}{MARK}: the Smart smoothing button, in the top bar\n"
            f"{indent}invoke-static {{p0}}, Lseekpatch/Smooth;->attach(Landroid/app/Activity;)V\n")
    tree.set(activity_path, text[:after_layout] + hook + text[after_layout:])

    for abi in abis:
        tree.add_native_library(abi, native.SMOOTH, native.library(abi))
    add_helpers(tree, "Smooth")
    others = [a for a in tree.abis if a not in abis]
    return [f"{tree.rel(call.path)}: Smooth.frame after the feature-900 call",
            f"{tree.rel(activity_path)}: the button after {activity.split('/')[-1][:-1]}.setContentView",
            f"lib/{{{','.join(abis)}}}/{native.SMOOTH}" + (f" (none for {', '.join(others)})" if others else "")]
