"""Where things live in the Seek Thermal app, found by what they do rather than by their
(obfuscated, per-release) names.  Shared by the patches.

The live view is drawn by a GL thread that names itself "ThermalPlusRenderThread" (q/g in 2.3.4,
com/tyriansystems/Seekware/OpenGL/RenderManager in 1.9.1, the one build with names kept).  It owns
the thermal texture upload: a (ByteBuffer, int width, int height) method around glTexImage2D.
"""
from __future__ import annotations

import re

from ..smali import Method, PatchError, SmaliTree, class_descriptor, methods

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
