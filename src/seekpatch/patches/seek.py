"""Where things live in the Seek Thermal app, found by what they do rather than by their
(obfuscated, per-release) names.  Shared by the patches.

The live view is drawn by a GL thread that names itself "ThermalPlusRenderThread" (q/g in 2.3.4,
com/tyriansystems/Seekware/OpenGL/RenderManager in 1.9.1, the one build with names kept).  It owns
the thermal texture upload: a (ByteBuffer, int width, int height) method around glTexImage2D.

Before every frame the camera pipeline sends the image library its features; the "Image smoothing"
switch goes out as feature 900 (featureEnhancedProcessing), which rewrites the filter-stage mask.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..smali import REG, Method, PatchError, SmaliTree, class_descriptor, method_at, methods
from .base import mark

GL_TEX_IMAGE = "Landroid/opengl/GLES20;->glTexImage2D(IIIIIIIILjava/nio/Buffer;)V"
ON_CREATE = "onCreate(Landroid/os/Bundle;)V"
SET_CONTENT_VIEW = "setContentView(I)V"
UPLOAD_SIG = "(Ljava/nio/ByteBuffer;II)V"
FEATURE_SIG = "(JILjava/nio/ByteBuffer;I)I"


def render_thread(tree: SmaliTree, patch: str) -> tuple[str, str]:
    """(path, class descriptor) of the live-view GL thread."""
    hits = tree.containing('"ThermalPlusRenderThread"')
    if len(hits) != 1:
        raise PatchError(f"{patch}: expected one ThermalPlusRenderThread class, found {len(hits)}"
                         " -- not a Seek Thermal 1.9 - 2.3 apk?")
    return hits[0], class_descriptor(tree.get(hits[0]))


def texture_upload(tree: SmaliTree, path: str, patch: str) -> Method:
    """The render thread's (ByteBuffer, w, h) -> glTexImage2D method."""
    found = [m for m in methods(tree.get(path)) if m.header.endswith(UPLOAD_SIG) and GL_TEX_IMAGE in m.body]
    if len(found) != 1:
        raise PatchError(f"{patch}: expected one ByteBuffer texture upload in {tree.rel(path)}, found {len(found)}")
    return found[0]


def upload_call(tree: SmaliTree, rpath: str, cls: str, patch: str) -> tuple[str, re.Match]:
    """The one call of the thermal upload -- direct / virtual, or through its static accessor --
    as (path, match): group(1) is its indent, group(2) the render thread instance, which is still in
    that register after the call.  The thermal-frame handler; code inserted after it runs per frame."""
    upload = texture_upload(tree, rpath, patch).descriptor
    accessor = static_accessors(tree, rpath, cls)
    targets = [(r"invoke-(?:direct|virtual)", upload)] + [(r"invoke-static", a) for a, t in accessor.items() if t == upload]
    c = re.escape(cls)
    sites = []
    for p in tree.containing(cls):
        text = tree.get(p)
        for op, name in targets:
            for s in re.finditer(r"^([ \t]*)" + op + r" \{(" + REG + "), " + REG + ", " + REG + ", " + REG + r"\}, "
                                 + c + "->" + re.escape(name) + r"\n", text, re.M):
                owner = method_at(text, s.start())
                if not (p == rpath and owner is not None and owner.is_static_synthetic):  # not the accessor itself
                    sites.append((p, s))
    if len(sites) != 1:
        raise PatchError(f"{patch}: expected one call of the upload {upload}, found {len(sites)}")
    return sites[0]


def static_accessors(tree: SmaliTree, path: str, cls: str) -> dict[str, str]:
    """Static synthetic accessors of cls (pre-2.3 inner classes reach private methods through them):
    accessor descriptor -> the descriptor it forwards to."""
    out = {}
    for m in methods(tree.get(path)):
        if m.is_static_synthetic:
            calls = re.findall(r"invoke-direct(?:/range)? \{[^}]*\}, " + re.escape(cls) + r"->([\w$]+\([^)]*\)\w)", m.body)
            if len(calls) == 1:
                out[m.descriptor] = calls[0]
    return out


def seekip_feature(tree: SmaliTree, patch: str, native: str) -> str:
    """A `native` ("seekIPsetFeature" / "seekIPgetFeature") another class can call: the native itself
    if public, else its public static wrapper."""
    found = []
    for p in tree.containing(f"{native}{FEATURE_SIG}"):
        cls = class_descriptor(tree.get(p))
        for m in methods(tree.get(p)):
            words = m.header.split()
            if "public" not in words or "static" not in words:  # called from another class
                continue
            if m.descriptor == f"{native}{FEATURE_SIG}" and "native" in words:
                found.append(f"{cls}->{m.descriptor}")
            elif ("native" not in words and m.descriptor.endswith(FEATURE_SIG)
                  and f"->{native}{FEATURE_SIG}" in m.body):
                found.append(f"{cls}->{m.descriptor}")
    if len(found) != 1:
        raise PatchError(f"{patch}: expected one callable {native}, found {found}")
    return found[0]


SEEKIP = "Lseekpatch/SeekIP;"
SEEKIP_SMALI = """.class public final Lseekpatch/SeekIP;
.super Ljava/lang/Object;
.source "seek-thermal-apk-patches {patch}"

{mark}: the app's own image-library feature calls, for seek-thermal-apk-patches' helpers


# direct methods
.method public static getFeature{sig}
    .locals 1

    invoke-static/range {{p0 .. p4}}, {getfeature}

    move-result v0

    return v0
.end method

.method public static setFeature{sig}
    .locals 1

    invoke-static/range {{p0 .. p4}}, {setfeature}

    move-result v0

    return v0
.end method
"""


def seekip_class(tree: SmaliTree, patch: str) -> tuple[str, str]:
    """seekpatch.SeekIP -- getFeature / setFeature, forwarding to the app's own feature calls -- for the
    Java helpers (helpers/stubs/seekpatch/SeekIP.java), added unless another patch did.  Returns the
    app's (setFeature, getFeature)."""
    setfeature = seekip_feature(tree, patch, "seekIPsetFeature")
    getfeature = seekip_feature(tree, patch, "seekIPgetFeature")
    if not tree.path_of(SEEKIP):
        tree.add_class(SEEKIP, SEEKIP_SMALI.format(patch=patch, mark=mark(patch), sig=FEATURE_SIG,
                                                   getfeature=getfeature, setfeature=setfeature))
    return setfeature, getfeature


@dataclass(frozen=True)
class FeatureCall:
    """The per-frame feature-900 call; code inserted at `end` runs right after it, once per frame."""
    path: str
    end: int
    indent: str
    cls: str     # the class that sends the features
    flag: str    # its "Image smoothing" switch field
    enum: str    # descriptor of the feature enum
    field: str   # the enum constant of featureEnhancedProcessing


def _feature_900(tree: SmaliTree, patch: str) -> tuple[str, str]:
    """(enum descriptor, field) of featureEnhancedProcessing; the enum constant names are obfuscated."""
    for p in tree.containing('"featureEnhancedProcessing"'):
        text = tree.get(p)
        enum = class_descriptor(text)
        m = re.search(r'const-string ' + REG + r', "featureEnhancedProcessing".*?sput-object ' + REG + ", "
                      + re.escape(enum) + r"->([\w$]+):" + re.escape(enum), text, re.S)
        if m:
            return enum, m.group(1)
    raise PatchError(f"{patch}: featureEnhancedProcessing enum constant not found")


def feature_900_call(tree: SmaliTree, patch: str) -> FeatureCall:
    """The call that sends feature 900 before every frame, in a method whose p1/p2 is the library handle."""
    enum, field = _feature_900(tree, patch)
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
        raise PatchError(f"{patch}: expected one feature-900 call, found {len(hits)}")
    path, h = hits[0]
    cls, flag, indent, lo, hi = h.group(3), h.group(4), h.group(7), h.group(8), h.group(9)
    if (lo, hi) != ("p1", "p2"):
        raise PatchError(f"{patch}: handle is in {lo}/{hi}, expected p1/p2 -- the per-frame feature method changed shape")
    if class_descriptor(tree.get(path)) != cls:
        raise PatchError(f"{patch}: the switch field lives in {cls}, not in the class that sends feature 900")
    return FeatureCall(path, h.end(), indent, cls, flag, enum, field)


def camera_activity(tree: SmaliTree, patch: str) -> tuple[str, int]:
    """The live view's activity: its onCreate sets the layout and looks up the SurfaceView.
    Returns (path, offset just past the setContentView call): views added there join the layout."""
    hits = []
    for p in tree.containing(SET_CONTENT_VIEW, "Landroid/view/SurfaceView;"):
        text = tree.get(p)
        for m in methods(text):
            if m.descriptor == ON_CREATE and SET_CONTENT_VIEW in m.body and "Landroid/view/SurfaceView;" in m.body:
                calls = list(re.finditer(r"^[ \t]*invoke-virtual \{p0, " + REG + r"\}, L[\w/$]+;->"
                                         + re.escape(SET_CONTENT_VIEW) + r"\n", text[m.start:m.end], re.M))
                hits += [(p, m.start, c) for c in calls]
    if len(hits) != 1:
        raise PatchError(f"{patch}: expected one setContentView in an onCreate that finds the SurfaceView, "
                         f"found {len(hits)}")
    path, offset, call = hits[0]
    return path, offset + call.end()
