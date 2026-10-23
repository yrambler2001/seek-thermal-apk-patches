"""Where things live in the Seek Thermal app, found by what they do rather than by their
(obfuscated, per-release) names.  Shared by the patches.

The live view is drawn by a GL thread that names itself "ThermalPlusRenderThread" (q/g in 2.3.4,
com/tyriansystems/Seekware/OpenGL/RenderManager in 1.9.1, the one build with names kept).  It owns
the thermal texture upload: a (ByteBuffer, int width, int height) method around glTexImage2D.
"""
from __future__ import annotations

import re

from ..smali import REG, Method, PatchError, SmaliTree, class_descriptor, method_at, methods

GL_TEX_IMAGE = "Landroid/opengl/GLES20;->glTexImage2D(IIIIIIIILjava/nio/Buffer;)V"
UPLOAD_SIG = "(Ljava/nio/ByteBuffer;II)V"


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

