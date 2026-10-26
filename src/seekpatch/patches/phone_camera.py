"""phone_camera: the phone's own rear camera runs only in Thermal+.

The live view's render thread owns a handler for the phone's camera (the thread "VisibleCameraHandlerThread"):

    render thread constructor   handler.openCamera(Context)              opens the camera
    render thread GL setup      handler.beginCameraPreview(SurfaceTexture)  (opens it if needed,) starts its preview
    render thread stop          handler.pausePreview()                   stops it, releases the camera
    front / back switch         handler.switch...(SurfaceTexture)        releases it, opens the other camera

(1.9.1's names; later releases obfuscate them, the calls are the same.)  So the camera runs whenever the
live view does, also in the plain thermal view, where nothing uses it: the stream blends it in only in
Thermal+ (its setUseThermalPlus(boolean) sets the blend to the Thermal+ amount or 0), and only a Thermal+
photo waits for its picture.  On a Pixel 8 Pro the unseen preview kept the camera HAL busy on more than a
CPU core, and Android gives an app with a camera open at most 60 Hz.

The patch (helpers/java/seekpatch/PhoneCamera.java):
1. drops the constructor's openCamera(Context) and replaces the GL setup's beginCameraPreview with
   PhoneCamera.ready(this): the camera stays closed;
2. setUseThermalPlus(boolean) first calls PhoneCamera.thermalPlus(renderThread, on), which runs the
   render thread's seekpatchCameraOn() (beginCameraPreview with its camera texture) or
   seekpatchCameraOff() (pausePreview) on a thread of its own;
3. the front / back switch does nothing while the camera is closed.

Without full_fps the live view is redrawn only for phone-camera frames, and without video_quality a
recording takes only phone-camera frames, so the patch needs both.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, class_descriptor, code_start, locals_count, methods
from .base import ensure_unpatched, mark
from .seek import render_thread

NAME = "phone_camera"
SUMMARY = "the phone's rear camera runs only in Thermal+: no hidden preview in the plain view, up to 120 Hz"
VERSIONS = "2.1.2 - 2.3.4"
RECOMMENDED = True
REQUIRES = ("full_fps", "video_quality")

MARK = mark(NAME)
CAMERA = "Lseekpatch/PhoneCamera;"
OWNER = "Lseekpatch/PhoneCamera$Owner;"
TEXTURE = "Landroid/graphics/SurfaceTexture;"


def _one(found: list, what: str):
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one {what}, found {len(found)}")
    return found[0]


def _handler_calls(text: str, handler: str, args: str):
    """(method, match) of every invoke-virtual {handler, x}, handler->name(args)V in a class."""
    call = re.compile(r"^([ \t]*)invoke-virtual \{(" + REG + r"), (" + REG + r")\}, " + re.escape(handler)
                      + r"->([\w$]+)\(" + re.escape(args) + r"\)V$", re.M)
    return [(m, c) for m in methods(text) for c in call.finditer(m.body)]


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    for need in REQUIRES:
        if not tree.containing(mark(need)):
            raise PatchError(f"{NAME}: needs {need} applied first")
    rpath, render = render_thread(tree, NAME)
    hpath = _one(tree.containing('"VisibleCameraHandlerThread"'), "phone-camera handler (VisibleCameraHandlerThread)")
    handler = class_descriptor(tree.get(hpath))
    text = tree.get(rpath)
    hfield = _one(re.findall(r"^\.field [^\n]*?([\w$]+):" + re.escape(handler) + "$", text, re.M),
                  f"phone-camera handler field in {tree.rel(rpath)}")
    tfield = _one(re.findall(r"^\.field [^\n]*?([\w$]+):" + re.escape(TEXTURE) + "$", text, re.M),
                  f"camera texture field in {tree.rel(rpath)}")

    opens = [(m, c) for m, c in _handler_calls(text, handler, "Landroid/content/Context;") if m.name == "<init>"]
    open_method, open_call = _one(opens, f"camera opened in the constructor of {tree.rel(rpath)}")
    starts = _handler_calls(text, handler, TEXTURE)
    start_method, start_call = _one([(m, c) for m, c in starts if "Landroid/view/Surface;Z)V" in m.body],
                                    f"camera preview started where {tree.rel(rpath)} makes its window surface")
    switches = [m for m, c in starts if m.name != start_method.name or m.descriptor != start_method.descriptor]
    stops = [m.name for m in methods(tree.get(hpath)) if m.descriptor.endswith("()V") and "Ljava/lang/Object;->wait()V" in m.body
             and "Landroid/os/Handler;->post(" in m.body]
    stop = _one(stops, f"camera stop (posts, then waits) in {tree.rel(hpath)}")
    if f"{handler}->{stop}()V" not in text:
        raise PatchError(f"{NAME}: {tree.rel(rpath)} never stops the camera with {stop}()")
    begin = start_call.group(4)

    # The stream's Thermal+ setter: stores p1 and sets the render thread's blend.
    setters = []
    for p in tree.containing(render):
        if p == rpath:
            continue
        for m in methods(tree.get(p)):
            fields = re.findall(r"iget-object " + REG + r", p0, L[\w/$]+;->([\w$]+):" + re.escape(render), m.body)
            if (m.descriptor.endswith("(Z)V") and "static" not in m.header.split() and fields
                    and re.search(r"iput-boolean p1, p0, ", m.body) and re.search(re.escape(render) + r"->[\w$]+\(F\)V", m.body)):
                setters.append((p, m, fields[0]))
    spath, setter, sfield = _one(setters, "Thermal+ setter (stores its boolean, sets the render thread's blend)")
    if locals_count(setter.body) < 1:
        raise PatchError(f"{NAME}: {tree.rel(spath)} {setter.name}() has no local register for the render thread")
    first_v0 = next((line for line in setter.body[code_start(setter.body):].splitlines()
                     if re.search(r"\bv0\b", line) and not line.strip().startswith("#")), "")
    if not re.match(r"[ \t]*(?:iget|sget|const|move-result|new-instance)[\w/-]* v0, ", first_v0):
        raise PatchError(f"{NAME}: {tree.rel(spath)} {setter.name}() reads v0 before setting it")

    # render thread: no camera in the constructor; ready() instead of the preview start; implements Owner
    edits = [(open_method, open_call, f"{open_call.group(1)}{MARK}: the phone's camera opens when Thermal+ goes on, not here"),
             (start_method, start_call, f"{start_call.group(1)}{MARK}: the camera's preview starts when Thermal+ goes on\n"
                                        f"{start_call.group(1)}invoke-static {{p0}}, {CAMERA}->ready({OWNER})V")]
    for m, c, new in sorted(edits, key=lambda e: -e[0].start):
        at = text.index("\n", m.start) + 1
        text = text[:at + c.start()] + new + text[at + c.end():]
    if ".super Landroid/os/HandlerThread;\n" not in text:
        raise PatchError(f"{NAME}: {tree.rel(rpath)} is not a HandlerThread")
    text = text.replace(".super Landroid/os/HandlerThread;\n", f".super Landroid/os/HandlerThread;\n.implements {OWNER}\n", 1)
    tree.set(rpath, text.rstrip("\n") + f"""

.method public seekpatchCameraOn()V
    .locals 2

    {MARK}: Thermal+ is on: start the phone camera's preview (the handler opens the camera)
    iget-object v0, p0, {render}->{hfield}:{handler}

    iget-object v1, p0, {render}->{tfield}:{TEXTURE}

    if-eqz v0, :seekpatch_none

    if-eqz v1, :seekpatch_none

    invoke-virtual {{v0, v1}}, {handler}->{begin}({TEXTURE})V

    :seekpatch_none
    return-void
.end method

.method public seekpatchCameraOff()V
    .locals 1

    {MARK}: Thermal+ is off: stop the preview and release the camera
    iget-object v0, p0, {render}->{hfield}:{handler}

    if-eqz v0, :seekpatch_none

    invoke-virtual {{v0}}, {handler}->{stop}()V

    :seekpatch_none
    return-void
.end method
""")
    out = [f"{tree.rel(rpath)}: no phone camera at start ({open_call.group(4)}(), {begin}() -> PhoneCamera.ready)",
           f"{tree.rel(rpath)}: seekpatchCameraOn() / seekpatchCameraOff() ({begin}() / {stop}())"]

    for m in switches:
        if not m.descriptor.endswith("()V") or locals_count(m.body) < 1:
            raise PatchError(f"{NAME}: the camera switch {m.name}{m.descriptor[m.descriptor.index('('):]} is not a void "
                             "no-argument method with a local register")
        text = tree.get(rpath)
        m = next(x for x in methods(text) if x.descriptor == m.descriptor)
        at = text.index("\n", m.start) + 1 + code_start(m.body)
        ind = re.match(r"[ \t]*", text[at:]).group(0)
        tree.set(rpath, text[:at] + f"{ind}{MARK}: no camera switch while the camera is closed\n"
                 f"{ind}invoke-static {{p0}}, {CAMERA}->isOpen(Ljava/lang/Object;)Z\n\n{ind}move-result v0\n\n"
                 f"{ind}if-nez v0, :seekpatch_open\n\n{ind}return-void\n\n{ind}:seekpatch_open\n" + text[at:])
        out.append(f"{tree.rel(rpath)} {m.name}(): the front / back switch only while the camera is open")

    text = tree.get(spath)
    m = next(x for x in methods(text) if x.descriptor == setter.descriptor)
    at = text.index("\n", m.start) + 1 + code_start(m.body)
    ind = re.match(r"[ \t]*", text[at:]).group(0)
    stream = class_descriptor(text)
    tree.set(spath, text[:at] + f"{ind}{MARK}: the phone's camera runs only in Thermal+\n"
             f"{ind}iget-object v0, p0, {stream}->{sfield}:{render}\n\n"
             f"{ind}invoke-static {{v0, p1}}, {CAMERA}->thermalPlus(Ljava/lang/Object;Z)V\n\n" + text[at:])
    out.append(f"{tree.rel(spath)} {setter.name}(): opens / closes the phone's camera with Thermal+")
    add_helpers(tree, "PhoneCamera")
    return out
