"""full_fps: draw every thermal frame, not every phone-camera frame.

The live view's GL thread has two inputs:

    thermal frame   upload the colorized frame into a texture (glTexImage2D) -- nothing else
    camera frame    SurfaceTexture.onFrameAvailable of the phone's *own* rear camera:
                    updateTexImage, feed the video encoder, then draw + eglSwapBuffers

so the screen is redrawn only when the phone camera delivers a frame.  The app opens the rear
camera even in the plain thermal view (it is the source for the Thermal+ overlay) and asks for the
preview fps range closest to 15-15, so on most phones the screen updates at exactly 15 fps while
the Compact delivers ~30 and every other thermal frame is replaced before it is shown.

This patch calls the draw right after the thermal upload and drops it from the camera handler.
The camera handler still latches the camera texture (Thermal+ blends the newest camera frame) and
still feeds the video encoder, so recordings keep the camera's clock.

Three call shapes across releases, all handled:
    2.3.x       both handlers are lambda methods of the render thread (invoke-direct {p0})
    2.1 - 2.2   inner Runnable classes reach private methods through static synthetic accessors
    1.9 - 2.0   inner classes call package-private methods with invoke-virtual
"""
from __future__ import annotations

import re

from ..smali import REG, PatchError, SmaliTree, methods
from .base import Options, ensure_unpatched, mark
from .seek import render_thread, static_accessors, texture_upload, upload_call

NAME = "full_fps"
SUMMARY = "draw every thermal frame instead of every phone-camera frame: live view 15 -> ~30 fps"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
UPDATE_TEX_IMAGE = "Landroid/graphics/SurfaceTexture;->updateTexImage()V"


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    rpath, cls = render_thread(tree, NAME)
    upload = texture_upload(tree, rpath, NAME).descriptor
    accessor = static_accessors(tree, rpath, cls)
    heads = {m.descriptor: m.header for m in methods(tree.get(rpath))}
    users = tree.containing(cls)
    c = re.escape(cls)

    # The camera-frame handler: the method with updateTexImage whose one no-arg void call into the
    # render thread is the draw.
    camera = []
    for p in users:
        for m in methods(tree.get(p)):
            if UPDATE_TEX_IMAGE not in m.body:
                continue
            for call in re.finditer(r"^[ \t]*invoke-(direct|virtual|static) \{(" + REG + r")\}, " + c
                                    + r"->([\w$]+)\((" + c + r")?\)V\n", m.body, re.M):
                kind, reg, name, arg = call.groups()
                if kind == "static" and arg:
                    target = accessor.get(f"{name}({cls})V")
                elif kind == "direct" and not arg and p == rpath and reg == "p0":
                    target = name + "()V"
                elif kind == "virtual" and not arg:
                    target = name + "()V"
                else:
                    continue
                if target in heads:
                    camera.append((p, m, call.group(0), target))
    if len(camera) != 1:
        raise PatchError(f"{NAME}: expected one camera-frame handler ending in a draw call, found {len(camera)}")
    cam_path, cam_method, cam_call, draw = camera[0]
    draw_private = "private" in heads[draw].split()

    # The thermal-frame handler: the one call of the upload, direct / virtual or through its accessor.
    site_path, site = upload_call(tree, rpath, cls, NAME)
    inst = site.group(2)  # the render thread instance, still in its register after the call
    if not draw_private:
        draw_call = f"invoke-virtual {{{inst}}}, {cls}->{draw}"
    elif site_path == rpath:
        draw_call = f"invoke-direct {{{inst}}}, {cls}->{draw}"
    else:
        accs = [a for a, t in accessor.items() if t == draw]
        if not accs:
            raise PatchError(f"{NAME}: {draw} is private and has no static accessor to call from {tree.rel(site_path)}")
        draw_call = f"invoke-static {{{inst}}}, {cls}->{accs[0]}"

    # 1. draw right after the thermal upload (inside the caller's try block, which releases the frame)
    ind = site.group(1)
    text = tree.get(site_path)
    tree.set(site_path, text[:site.end()] + f"\n{ind}{MARK}: present every thermal frame\n{ind}{draw_call}\n"
             + text[site.end():])
    # 2. no draw per camera frame
    indent = re.match(r"[ \t]*", cam_call).group(0)
    fresh = next(m for m in methods(tree.get(cam_path)) if m.body == cam_method.body)
    tree.replace_method_body(cam_path, fresh, cam_method.body.replace(
        cam_call, f"{indent}{MARK}: no redraw per camera frame (thermal frames draw)\n", 1))
    return [f"render thread {cls}: upload {upload}, draw {draw}",
            f"{tree.rel(site_path)}: draw after the upload; {tree.rel(cam_path)}: no draw per camera frame"]
