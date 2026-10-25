"""nano: the Seek Nano 300 works in the app.

The Nano 300 is a Compact Pro inside (USB 289d:0011, "PIR324 Thermal Camera"): the app takes it for one
and connects, but the live view stays black, for two reasons:
  - its firmware sends no frames until it is unlocked: USB vendor request 55 with {252, 4}, which Seek's
    Nano app sends (seekcamera_nano_unlock) to the cameras whose core part number is a Nano's;
  - it sends each frame in pieces of 6840 bytes (10 rows) where a Compact Pro sends 13680, and the app
    reads a frame in chunks of the size it expects: each chunk gets half its bytes, the frame its rows in
    the wrong places, and libseekip rejects it (SeekIPprocess returned 1407).

The patch adds:
    a call where the app sets the camera's operation mode   Nano.unlock(connection, mode): before run, a
                                                             289d:0011 camera's core part number is read
                                                             and a Nano 300 (CQ-ABAX, LQ-ABAX, CQ-DBAX)
                                                             is unlocked
    the app's chunk size for a frame                         Nano.chunk(size): 6840 for a Nano 300

A Compact Pro is left as it was.

Versions: the operation-mode request and the chunk size look the same in every release from 2.0; 1.9.x
has no 320x240 camera.  Older releases than 2.1.5 carry firmware they write to a 289d:0011 camera whose
version they do not expect, so the patch refuses them.
Sources: helpers/java/seekpatch/Nano.java; see docs/nano.md.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, code_start, methods
from .base import Options, ensure_unpatched, mark

NAME = "nano"
SUMMARY = "the Seek Nano 300 works: it is unlocked and its frames read in its own chunk size"
VERSIONS = "2.1.5 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
NANO = "Lseekpatch/Nano;"
CONNECTION = "Landroid/hardware/usb/UsbDeviceConnection;"
CONTROL = CONNECTION + "->controlTransfer(IIII[BII)I"
SET_OPERATION_MODE = 0x3c  # the camera's request that sets sleep / run
GET_FRAME = 0x53           # the camera's request for one frame
QUEUE = "Landroid/hardware/usb/UsbRequest;->queue(Ljava/nio/ByteBuffer;I)Z"
REQUEST_WAIT = "Landroid/hardware/usb/UsbDeviceConnection;->requestWait()Landroid/hardware/usb/UsbRequest;"
CHUNK_ERROR = "determine frame-data chunk size"  # the method's exception for an unknown camera
# the image library's process call: handle, element sizes, counts, raw, filtered, thermography, color, results
PROCESS = ("JLjava/nio/IntBuffer;Ljava/nio/IntBuffer;Ljava/nio/ByteBuffer;Ljava/nio/ByteBuffer;"
           "Ljava/nio/FloatBuffer;Ljava/nio/ByteBuffer;Ljava/nio/ByteBuffer;")
ORIENT = PROCESS[len("JLjava/nio/IntBuffer;"):]
SET_FEATURE = "JILjava/nio/ByteBuffer;I"  # handle, id, value, length
MIN_VERSION_CODE = 217  # 2.1.5: 1.9.1 - 2.1.4 carry camera firmware they write to a 289d:0011 camera unasked


def _operation_mode(tree: SmaliTree) -> str:
    """Nano.unlock at the top of the method that sets the operation mode:
    controlTransfer(0x41, 0x3c, 0, 0, mode, 2, timeout), the connection in p1 and the mode in p2."""
    want = re.compile(r"^[ \t]*const/16 " + REG + f", {SET_OPERATION_MODE:#x}\n", re.M)
    sites = [(p, m) for p in tree.containing(CONTROL) for m in methods(tree.get(p))
             if m.descriptor.endswith(f"({CONNECTION}[B)I") and CONTROL in m.body and want.search(m.body)]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one method setting the camera's operation mode "
                         f"(request {SET_OPERATION_MODE:#x}), found {len(sites)}")
    path, m = sites[0]
    if "static" in m.header.split():
        raise PatchError(f"{NAME}: the operation-mode request is static, so its connection is not p1")
    text = tree.get(path)
    at = text.index("\n", m.start) + 1 + code_start(m.body)
    indent = re.match(r"[ \t]*", text[at:]).group(0)
    hook = (f"{indent}{MARK}: a Nano 300 is unlocked before it is set to run\n"
            f"{indent}invoke-static {{p1, p2}}, {NANO}->unlock({CONNECTION}[B)V\n\n")
    tree.set(path, text[:at] + hook + text[at:])
    return f"{tree.rel(path)} {m.name}()"


def _chunk(tree: SmaliTree) -> str:
    """Each value the chunk-size method returns (16224 for 289d:0010, 13680 for 289d:0011) goes
    through Nano.chunk."""
    sites = [(p, m) for p in tree.containing(CHUNK_ERROR) for m in methods(tree.get(p))
             if CHUNK_ERROR in m.body and m.descriptor.endswith("()I")]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one method choosing the frame's chunk size, found {len(sites)}")
    path, m = sites[0]
    ret = re.compile(r"^([ \t]*)return (" + REG + r")\n", re.M)
    if not ret.search(m.body):
        raise PatchError(f"{NAME}: the chunk-size method returns no register")
    body = ret.sub(lambda r: (f"{r.group(1)}{MARK}: a Nano 300's piece size\n"
                              f"{r.group(1)}invoke-static {{{r.group(2)}}}, {NANO}->chunk(I)I\n\n"
                              f"{r.group(1)}move-result {r.group(2)}\n\n"
                              f"{r.group(1)}return {r.group(2)}\n"), m.body)
    tree.replace_method_body(path, m, body)
    return f"{tree.rel(path)} {m.name}()"


def _orientation(tree: SmaliTree) -> str:
    """Nano.orient after the wrapper's call to the image library's process: the wrapper is static and
    passes its own arguments on (handle J, sizes, counts, raw, filtered, thermography, color, results),
    so p3 - p8 are the counts to the results."""
    want = re.compile(r"^[ \t]*invoke-static(?:/range)? \{[^}]*\}, L[\w/$]+;->seekIPprocess\(" + re.escape(PROCESS)
                      + r"\)I\n(?:[ \t]*(?:\.line \d+)?[ \t]*\n)*([ \t]*)move-result " + REG + r"\n", re.M)
    sites = [(p, m, h) for p in tree.containing("->seekIPprocess(") for m in methods(tree.get(p))
             if "native" not in m.header.split() for h in [want.search(m.body)] if h]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one call to the image library's process, found {len(sites)}")
    path, m, h = sites[0]
    if "static" not in m.header.split() or not m.descriptor.endswith(f"({PROCESS})I"):
        raise PatchError(f"{NAME}: the process call is not in a static wrapper taking the same arguments")
    indent = h.group(1)
    hook = (f"\n{indent}{MARK}: a Nano 300's picture right side up\n"
            f"{indent}invoke-static/range {{p3 .. p8}}, {NANO}->orient({ORIENT})V\n")
    tree.replace_method_body(path, m, m.body[:h.end()] + hook + m.body[h.end():])
    return f"{tree.rel(path)} {m.name}()"


def _features(tree: SmaliTree) -> str:
    """Nano.feature before the wrapper's call to the image library's setfeature: the wrapper is static
    and passes its own arguments on (handle J, id, value, length); the id it sends is Nano.feature's."""
    want = re.compile(r"^([ \t]*)invoke-static(?:/range)? \{[^}]*\}, L[\w/$]+;->seekIPsetFeature\(" + re.escape(SET_FEATURE)
                      + r"\)I\n", re.M)
    sites = [(p, m, h) for p in tree.containing("->seekIPsetFeature(") for m in methods(tree.get(p))
             if "native" not in m.header.split() for h in [want.search(m.body)] if h]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one call to the image library's setfeature, found {len(sites)}")
    path, m, h = sites[0]
    if "static" not in m.header.split() or not m.descriptor.endswith(f"({SET_FEATURE})I"):
        raise PatchError(f"{NAME}: the setfeature call is not in a static wrapper taking the same arguments")
    indent = h.group(1)
    hook = (f"{indent}{MARK}: a Nano 300 in SeekVision, as in Seek's Nano app\n"
            f"{indent}invoke-static/range {{p0 .. p4}}, {NANO}->feature({SET_FEATURE})I\n\n"
            f"{indent}move-result p2\n\n")
    tree.replace_method_body(path, m, m.body[:h.start()] + hook + m.body[h.start():])
    return f"{tree.rel(path)} {m.name}()"


def _frame_reading(tree: SmaliTree) -> list[str]:
    """The frame thread's piece queueing and waiting go through Nano.queue / Nano.requestWait (same
    registers, same results), and its frame request (0x53, the connection in p1) starts with Nano.frame."""
    done = []
    for call, helper in ((QUEUE, f"{NANO}->queue(Landroid/hardware/usb/UsbRequest;Ljava/nio/ByteBuffer;I)Z"),
                         (REQUEST_WAIT, f"{NANO}->requestWait({CONNECTION})Landroid/hardware/usb/UsbRequest;")):
        want = re.compile(r"^([ \t]*)invoke-virtual (\{[^}]*\}), " + re.escape(call) + r"\n", re.M)
        sites = [(p, m, h) for p in tree.containing(call) for m in methods(tree.get(p)) for h in want.finditer(m.body)]
        if len(sites) != 1:
            raise PatchError(f"{NAME}: expected one {call.split('->')[1].split('(')[0]}() in the frame thread, found {len(sites)}")
        path, m, h = sites[0]
        hook = (f"{h.group(1)}{MARK}: a Nano 300 that stops half way through a frame does not freeze the view\n"
                f"{h.group(1)}invoke-static {h.group(2)}, {helper}\n")
        tree.replace_method_body(path, m, m.body[:h.start()] + hook + m.body[h.end():])
        done.append(f"{tree.rel(path)} {m.name}()")
    want = re.compile(r"^[ \t]*const/16 " + REG + f", {GET_FRAME:#x}\n", re.M)
    sites = [(p, m) for p in tree.containing(CONTROL) for m in methods(tree.get(p))
             if m.descriptor.endswith(f"({CONNECTION}I)I") and CONTROL in m.body and want.search(m.body)
             and "static" not in m.header.split()]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one method asking the camera for a frame (request {GET_FRAME:#x}), "
                         f"found {len(sites)}")
    path, m = sites[0]
    text = tree.get(path)
    at = text.index("\n", m.start) + 1 + code_start(m.body)
    indent = re.match(r"[ \t]*", text[at:]).group(0)
    tree.set(path, text[:at] + f"{indent}{MARK}: a new frame\n{indent}invoke-static {{p1}}, {NANO}->frame({CONNECTION})V\n\n"
             + text[at:])
    done.append(f"{tree.rel(path)} {m.name}()")
    return done


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version; before 2.1.5 the app writes its own firmware to the camera")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) carries Compact Pro firmware "
                         f"it would write to a Nano 300 unasked (apps before 2.1.5)")
    mode = _operation_mode(tree)
    chunk = _chunk(tree)
    orientation = _orientation(tree)
    features = _features(tree)
    queue, wait, frame = _frame_reading(tree)
    add_helpers(tree, "Nano")
    return [f"{mode}: Nano.unlock before the operation mode is set",
            f"{chunk}: the chunk size through Nano.chunk",
            f"{orientation}: Nano.orient after the image library's process",
            f"{features}: Nano.feature before the image library's setfeature",
            f"{queue} / {wait} / {frame}: a frame's pieces through Nano.queue / Nano.requestWait, Nano.frame "
            f"before each frame request"]
