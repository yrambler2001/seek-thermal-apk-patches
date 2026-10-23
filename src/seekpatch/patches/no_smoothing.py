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

Versions: the feature ids and masks above are verified in libseekip 2.10.5.0 (app 2.2.2) and
2.11.3.2 (2.2.3 - 2.3.4); 2.2.0 / 2.2.1 carry the same preset code.  Older apps (2.1.x) bundle a
library whose feature 900 works differently, so the patch refuses them.
"""
from __future__ import annotations

import re

from ..smali import REG, AlreadyApplied, PatchError, SmaliTree, class_descriptor, methods
from .base import Options, ensure_unpatched, mark

NAME = "no_smoothing"
SUMMARY = 'make the "Image smoothing" switch really turn smoothing off (no temporal / spatial filter)'
VERSIONS = "2.2.0 - 2.3.4"
MIN_VERSION_CODE = 260  # 2.2.0
RECOMMENDED = True

MARK = mark(NAME)
SETFEATURE_SIG = "(JILjava/nio/ByteBuffer;I)I"

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


def _feature_900(tree: SmaliTree) -> tuple[str, str]:
    """(enum descriptor, field) of featureEnhancedProcessing; the enum constant names are obfuscated."""
    for p in tree.containing('"featureEnhancedProcessing"'):
        text = tree.get(p)
        enum = class_descriptor(text)
        m = re.search(r'const-string ' + REG + r', "featureEnhancedProcessing".*?sput-object ' + REG + ", "
                      + re.escape(enum) + r"->([\w$]+):" + re.escape(enum), text, re.S)
        if m:
            return enum, m.group(1)
    raise PatchError(f"{NAME}: featureEnhancedProcessing enum constant not found")


def _setfeature(tree: SmaliTree) -> str:
    """A seekIPsetFeature another class can call: the native itself if public, else its public static wrapper."""
    found = []
    for p in tree.containing(f"seekIPsetFeature{SETFEATURE_SIG}"):
        cls = class_descriptor(tree.get(p))
        for m in methods(tree.get(p)):
            words = m.header.split()
            if "public" not in words or "static" not in words:  # called from another class
                continue
            if m.descriptor == f"seekIPsetFeature{SETFEATURE_SIG}" and "native" in words:
                found.append(f"{cls}->{m.descriptor}")
            elif ("native" not in words and m.descriptor.endswith(SETFEATURE_SIG)
                  and f"->seekIPsetFeature{SETFEATURE_SIG}" in m.body):
                found.append(f"{cls}->{m.descriptor}")
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one callable seekIPsetFeature, found {found}")
    return found[0]


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    if tree.containing("nosmoothing_apply("):  # the same hook from an earlier tools/repack build
        raise AlreadyApplied(f"{NAME}: already applied (by an earlier no_smoothing build)")
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version, and the patch is only verified on 2.2.0 - 2.3.4")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) predates the image "
                         "library whose feature 900 the patch is verified on (apps 2.2.0 - 2.3.4)")
    enum, field = _feature_900(tree)
    setfeature = _setfeature(tree)
    e = re.escape(enum)
    # sget-object vA, <enum>-><900>; iget-boolean vB, p0, <cls>-><flag>:Z;
    # [ up to 2.3.0 the switch is passed as  flag ? 1 : 0 :  if-eqz vB / const 1 / goto / const 0 ]
    # invoke-direct {p0, p1, p2, vA, vB}, <cls>->set(J<enum>I)V      (handle = p1/p2, a long)
    gap = r"(?:[ \t]*(?:\.line \d+)?[ \t]*\n)*"
    call = re.compile(
        r"sget-object (" + REG + "), " + e + "->" + re.escape(field) + ":" + e + r"\n" + gap +
        r"[ \t]*iget-boolean (" + REG + r"), p0, (L[\w/$]+;)->([\w$]+):Z\n" + gap +
        r"(?:[ \t]*if-eqz \2, :(\w+)\n" + gap + r"[ \t]*const/4 \2, 0x1\n" + gap + r"[ \t]*goto :(\w+)\n" + gap +
        r"[ \t]*:\5\n" + gap + r"[ \t]*const/4 \2, 0x0\n" + gap + r"[ \t]*:\6\n" + gap + ")?"
        r"([ \t]*)invoke-direct \{p0, (p\d+), (p\d+), \1, \2\}, \3->[\w$]+\(J" + e + r"I\)V\n")
    hits = [(p, m) for p in tree.containing(f"{enum}->{field}:") for m in call.finditer(tree.get(p))]
    if len(hits) != 1:
        raise PatchError(f"{NAME}: expected one feature-900 call, found {len(hits)}")
    path, h = hits[0]
    cls, flag, indent, lo, hi = h.group(3), h.group(4), h.group(7), h.group(8), h.group(9)
    if (lo, hi) != ("p1", "p2"):
        raise PatchError(f"{NAME}: handle is in {lo}/{hi}, expected p1/p2 -- the per-frame feature method changed shape")
    if class_descriptor(tree.get(path)) != cls:
        raise PatchError(f"{NAME}: the switch field lives in {cls}, not in the class that sends feature 900")
    text = tree.get(path)
    hook = f"\n{indent}{MARK}\n{indent}invoke-static/range {{p0 .. {hi}}}, {cls}->seekpatch_nosmoothing_apply({cls}J)V\n"
    text = text[:h.end()] + hook + text[h.end():]
    text = text.rstrip("\n") + "\n" + HELPERS.format(mark=MARK, cls=cls, flag=flag, setfeature=setfeature)
    tree.set(path, text)
    return [f"featureEnhancedProcessing = {enum}->{field}, switch = {cls}->{flag}:Z, setFeature = {setfeature}",
            f"{tree.rel(path)}: hook after the feature-900 call, +2 helper methods"]
