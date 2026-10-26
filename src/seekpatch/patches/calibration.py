"""calibration: a "k·x+b" button, your own linear correction of every temperature the app shows and saves.

shown = k × measured + b, set from a reference thermometer, say.  The correction is made where libseekip
turns each frame into degrees (thermography_process: the per-pixel image and the spot, minimum and
maximum), so the readouts, the temperature bar, saved images and the library's own temperature-driven
coloring later in the frame (Span & Level, the isotherm modes) all see the corrected values.  k and b
are kept in °C and stay set until changed; b is entered and shown in the app's unit.

The patch adds:
    lib/<abi>/libseekpatch_calib.so               a hook on libseekip's PLT slot for thermography_process:
                                                  calls it, then maps its outputs through k × t + b
    a button below the camera screen's top bar   seekpatch.Calib.attach, after setContentView (left side)
    a call right after the per-frame feature 900  seekpatch.Calib.frame(): hooks the library once a
                                                  correction is set, then passes changes on

Versions: libseekip calls thermography_process through its PLT from 2.2.3 on (libseekip 2.11.3.2); the
hook also checks at run time that thermography_process and thermography_getfeature have the sizes of a
verified build (arm64-v8a, and armeabi-v7a of 2.2.3 - 2.3.0 and of 2.3.3 - 2.3.4).  Built for arm64-v8a
and armeabi-v7a only.  Sources: helpers/native/calib.c, helpers/java/seekpatch/Calib.java; see
docs/calibration.md.
"""
from __future__ import annotations

import re

from .. import native
from ..helpers import add_helpers
from ..smali import PatchError, SmaliTree, class_descriptor
from .base import ensure_unpatched, mark
from .seek import camera_activity, feature_900_call

NAME = "calibration"
SUMMARY = 'a "k·x+b" button: your own linear correction of every temperature the app shows and saves'
VERSIONS = "2.2.3 - 2.3.4"
MIN_VERSION_CODE = 276  # 2.2.3
RECOMMENDED = True

MARK = mark(NAME)
CALIB = "Lseekpatch/Calib;"
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
    hook = (f"\n{call.indent}{MARK}: hook the library once a correction is set, pass changes on\n"
            f"{call.indent}invoke-static {{}}, {CALIB}->frame()V\n")
    tree.set(call.path, text[:call.end] + hook + text[call.end:])

    text = tree.get(activity_path)
    indent = re.match(r"[ \t]*", text[text.rfind("\n", 0, after_layout - 1) + 1:]).group(0)
    hook = (f"\n{indent}{MARK}: the k·x+b button, below the top bar\n"
            f"{indent}invoke-static {{p0}}, {CALIB}->attach(Landroid/app/Activity;)V\n")
    tree.set(activity_path, text[:after_layout] + hook + text[after_layout:])

    for abi in abis:
        tree.add_native_library(abi, native.CALIB, native.library(abi, native.CALIB))
    add_helpers(tree, "Calib", "Floating")
    others = [a for a in tree.abis if a not in abis]
    return [f"{tree.rel(call.path)}: Calib.frame after the feature-900 call",
            f"{tree.rel(activity_path)}: the button after {activity.split('/')[-1][:-1]}.setContentView",
            f"lib/{{{','.join(abis)}}}/{native.CALIB}" + (f" (none for {', '.join(others)})" if others else "")]
