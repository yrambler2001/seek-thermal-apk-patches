"""no_smoothing: make the "Image smoothing" switch really turn smoothing off.

Before every frame the app sends feature 900 (featureEnhancedProcessing) = the "Image smoothing"
switch.  libseekip turns 900 into a filter-stage preset (seekip_setfeature case 900):

    switch on  (1) -> mask 0x86            sbnuc + alpf + gradient
    switch off (0) -> mask 0xC4 / 0x1C4    alpf + peaklimit + gradient (+ aslpf on non-1401 sensors)

so the temporal filter alpf (bit 0x4: pulls each pixel toward the previous frame's value) runs in
both positions, and "off" even *adds* the spatial 3x3 lowpass aslpf (bit 0x100) -- the switch off
is the smoother picture.  iOS has the same mapping.

This patch follows the 900 call with, when the switch is off:
    feature 102 = 0   clear bit 0x004  alpf  (temporal smoothing)
    feature 100 = 0   clear bit 0x100  aslpf (spatial 3x3 smoothing)
The "on" position keeps the stock preset; the rest of the "off" preset (gradient, peaklimit) stays.

Not in the default set since smoothing_settings, which replaces the switch with one per filter;
this patch is the alternative that keeps the single switch.  The two refuse to combine.

Versions: the feature ids and masks above are verified in libseekip 2.10.5.0 (app 2.2.2) and
2.11.3.2 (2.2.3 - 2.3.4); 2.2.0 / 2.2.1 carry the same preset code.  Older apps (2.1.x) bundle a
library whose feature 900 works differently, so the patch refuses them.
"""
from __future__ import annotations

from ..smali import AlreadyApplied, PatchError, SmaliTree
from .base import Options, ensure_unpatched, mark
from .seek import feature_900_call, seekip_feature

NAME = "no_smoothing"
SUMMARY = 'make the "Image smoothing" switch really turn smoothing off (no temporal / spatial filter)'
VERSIONS = "2.2.0 - 2.3.4"
MIN_VERSION_CODE = 260  # 2.2.0
RECOMMENDED = False  # the alternative to smoothing_settings
CONFLICTS = ("smoothing_settings",)

MARK = mark(NAME)

HELPERS = """
{mark}: called right after the feature-900 preset; clears alpf (102) and aslpf (100) when off
.method private static seekpatch_nosmoothing_apply({cls}J)V
    .locals 1

    iget-boolean v0, p0, {cls}->{flag}:Z
    if-nez v0, :keep

    const/16 v0, 0x66
    invoke-static {{p1, p2, v0}}, {cls}->seekpatch_nosmoothing_off(JI)V

    const/16 v0, 0x64
    invoke-static {{p1, p2, v0}}, {cls}->seekpatch_nosmoothing_off(JI)V

    :keep
    return-void
.end method

{mark}: seekIPsetFeature(handle, feature, int 0) -- the same buffer shape the app uses
.method private static seekpatch_nosmoothing_off(JI)V
    .locals 2

    const/4 v0, 0x4
    invoke-static {{v0}}, Ljava/nio/ByteBuffer;->allocateDirect(I)Ljava/nio/ByteBuffer;
    move-result-object v0
    sget-object v1, Ljava/nio/ByteOrder;->LITTLE_ENDIAN:Ljava/nio/ByteOrder;
    invoke-virtual {{v0, v1}}, Ljava/nio/ByteBuffer;->order(Ljava/nio/ByteOrder;)Ljava/nio/ByteBuffer;
    move-result-object v0
    const/4 v1, 0x0
    invoke-virtual {{v0, v1}}, Ljava/nio/ByteBuffer;->putInt(I)Ljava/nio/ByteBuffer;
    const/4 v1, 0x4
    invoke-static {{p0, p1, p2, v0, v1}}, {setfeature}
    return-void
.end method
"""


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    if tree.containing("nosmoothing_apply("):  # the same hook from an earlier tools/repack build
        raise AlreadyApplied(f"{NAME}: already applied (by an earlier no_smoothing build)")
    for other in CONFLICTS:
        if tree.containing(mark(other)):
            raise PatchError(f"{NAME}: {other} is applied, and the two are alternatives -- pick one")
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version, and the patch is only verified on 2.2.0 - 2.3.4")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) predates the image "
                         "library whose feature 900 the patch is verified on (apps 2.2.0 - 2.3.4)")
    call = feature_900_call(tree, NAME)
    setfeature = seekip_feature(tree, NAME, "seekIPsetFeature")
    cls, indent = call.cls, call.indent
    text = tree.get(call.path)
    hook = f"\n{indent}{MARK}\n{indent}invoke-static/range {{p0 .. p2}}, {cls}->seekpatch_nosmoothing_apply({cls}J)V\n"
    text = text[:call.end] + hook + text[call.end:]
    text = text.rstrip("\n") + "\n" + HELPERS.format(mark=MARK, cls=cls, flag=call.flag, setfeature=setfeature)
    tree.set(call.path, text)
    return [f"featureEnhancedProcessing = {call.enum}->{call.field}, switch = {cls}->{call.flag}:Z, "
            f"setFeature = {setfeature}",
            f"{tree.rel(call.path)}: hook after the feature-900 call, +2 helper methods"]
