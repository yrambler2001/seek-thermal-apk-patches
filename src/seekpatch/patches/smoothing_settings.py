"""smoothing_settings: a switch for each of Seek's image filters (and Smart smoothing) in
Settings -> Image & Video, in place of the "Image smoothing" switch.

Before every frame the app sends feature 900 (featureEnhancedProcessing) = the "Image smoothing"
switch.  libseekip's seekip_setfeature case 900 stores the value (read back only by getfeature 900)
and sets the first filter's stage mask:

    1 (on)  -> 0x86              sbnuc 0x2 + alpf 0x4 + gradient 0x80
    0 (off) -> 0x1C4 (0xC4)      alpf + peaklimit 0x40 + gradient + aslpf 0x100 (not on 1401 sensors)

then applies per-model defaults that are the same in both positions (filter and gradient-stage
features for some OEM cores, the mosaic cores' gradient moved to the second filter).  The first
filter runs before the temperatures are computed, so every stage shapes the readings too.

The patch adds:
    Default temporal smoothing          alpf  (feature 102), on by default
    Default spatial smoothing (3x3)     aslpf (feature 100), off
    Default pattern correction          sbnuc (feature 106), on
    Smart smoothing, Stripe correction,  the smart_smoothing patch's button and filter options, when
    Left-edge levelling                  that patch is in the app too (they share its stored values)
and hides the old switch.  Right after the app's feature-900 call, seekpatch.Filters.frame makes
the "on" preset the base (900 = 1 again if the app sent 0: the hidden switch may still hold off),
then sends 102 / 100 / 106 for the switches that are away from their default.  All at their
defaults is exactly the stock "Image smoothing on".  Peak limiting, part of the old "off" preset,
gets no switch: the "on" base does not run it.

The values are kept in the "seekpatch" preferences file; the settings hooks are shared with
sharp_scaling and video_quality (settings.py).  no_smoothing is the opt-in alternative (it changes
what the old switch does); the two refuse to combine.

Versions: the feature ids and presets are verified in libseekip 2.10.5.0 (app 2.2.2) and 2.11.3.2
(2.2.3 - 2.3.4), as for no_smoothing.  The old switch also appears in a legacy ImagePreference
(res/xml/pref_settings.xml), which 2.2.0 - 2.2.2 load only in a SettingsActivity nothing starts,
and 2.2.3+ not at all: it is never on screen, so it is left alone.  Sources:
helpers/java/seekpatch/{Filters,Settings}.java; see docs/smoothing-settings.md.
"""
from __future__ import annotations

from ..helpers import add_helpers
from ..smali import PatchError, SmaliTree
from .base import Options, ensure_unpatched, mark
from .seek import feature_900_call, seekip_class
from .settings import install as install_settings

NAME = "smoothing_settings"
SUMMARY = "Settings switches for Seek's temporal / spatial smoothing and pattern correction, and Smart smoothing"
VERSIONS = "2.2.0 - 2.3.4"
MIN_VERSION_CODE = 260  # 2.2.0
RECOMMENDED = True
CONFLICTS = ("no_smoothing",)

MARK = mark(NAME)

HELPER = """
{mark}: right after the feature-900 call, with the value it sent
.method private static seekpatch_filters({cls}J)V
    .locals 1

    iget-boolean v0, p0, {cls}->{flag}:Z
    invoke-static {{p1, p2, v0}}, Lseekpatch/Filters;->frame(JZ)V
    return-void
.end method
"""


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    for other in CONFLICTS:
        if tree.containing(mark(other)):
            raise PatchError(f"{NAME}: {other} is applied, and the two are alternatives -- pick one")
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version, and the patch is only verified on {VERSIONS}")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) predates the image "
                         f"library whose feature 900 the patch is verified on (apps {VERSIONS})")
    call = feature_900_call(tree, NAME)
    setfeature, _ = seekip_class(tree, NAME)
    report = install_settings(tree, NAME)

    cls, indent = call.cls, call.indent
    text = tree.get(call.path)
    hook = (f"\n{indent}{MARK}: Seek's filters as the settings say\n"
            f"{indent}invoke-static/range {{p0 .. p2}}, {cls}->seekpatch_filters({cls}J)V\n")
    text = text[:call.end] + hook + text[call.end:]
    text = text.rstrip("\n") + "\n" + HELPER.format(mark=MARK, cls=cls, flag=call.flag)
    tree.set(call.path, text)
    add_helpers(tree, "Filters")
    return [f"{tree.rel(call.path)}: Filters.frame after the feature-900 call (switch {cls}->{call.flag}:Z); "
            f"features via {setfeature}", *report]
