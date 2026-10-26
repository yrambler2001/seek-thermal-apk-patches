"""usb_queue: the camera's frames are read without gaps between them.

The camera library reads a frame like this (2.3.4; every release since 1.9.1 has the same code):

    frame request    control transfer 0x41 / 0x53, the frame's length in half-words
    chunks           4 USB requests on the Compact (13 on the CompactPRO), queued one at a time:
                     queue chunk i, requestWait(), queue chunk i + 1, ...
    next frame       the USB thread wakes the library's frame loop, which posts the next frame
                     request back to the USB thread

The camera starts sending a frame only while a frame request is waiting, and only during about the
first quarter of a sensor frame (FW-V1 compact_8hz_1_3_0_0: stream_push_chunk starts a frame up to
line 10 of 40); a later request waits for the next sensor frame, a 62 ms gap at 32 fps.  So the
next request has to go out as soon as the last chunk is in.

The patch keeps the library's code and changes three calls (helpers/java/seekpatch/UsbQueue.java):
1. the frame request becomes UsbQueue.frameRequest(), the same transfer, skipped when the next
   frame is already requested;
2. UsbRequest.queue() becomes UsbQueue.queue(): the first chunk's request also queues every other
   chunk of the frame, in order, so the phone always has a request waiting for the camera's data;
3. after requestWait(), UsbQueue.arrived(): when the frame's last chunk is in, the next frame
   request goes out at once, from the USB thread, before the library looks at the chunk.
The frame buffer class gets seekpatchChunks() (its chunk arrays) for 2.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, methods, register_number
from .base import Options, ensure_unpatched, mark

NAME = "usb_queue"
SUMMARY = "camera frames read without gaps: every chunk queued at once, the next frame requested as the last chunk lands"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = False

MARK = mark(NAME)
QUEUE_HELPER = "Lseekpatch/UsbQueue;"
FRAME = "Lseekpatch/UsbQueue$Frame;"
CONNECTION = "Landroid/hardware/usb/UsbDeviceConnection;"
REQUEST = "Landroid/hardware/usb/UsbRequest;"
QUEUE = REQUEST + "->queue(Ljava/nio/ByteBuffer;I)Z"
REQUEST_WAIT = CONNECTION + "->requestWait()" + REQUEST

FRAME_REQUEST_CALL = re.compile(r"^([ \t]*)invoke-virtual \{(" + REG + "), (" + REG + "), (" + REG + r")\}, (L[\w/$]+;)->([\w$]+)\("
                                + re.escape(CONNECTION) + r"I\)I$", re.M)
QUEUE_CALL = re.compile(r"^([ \t]*)invoke-virtual \{(" + REG + "), (" + REG + "), (" + REG + r")\}, " + re.escape(QUEUE) + "$", re.M)
WAIT_CALL = re.compile(r"^([ \t]*)invoke-virtual \{" + REG + r"\}, " + re.escape(REQUEST_WAIT) + r"\n"
                       r"(?:[ \t]*(?:\.line \d+)?\n)*[ \t]*move-result-object (" + REG + r")\n", re.M)


def _one(found: list, what: str):
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one {what}, found {len(found)}")
    return found[0]


def _writes(lines: str, reg: str) -> bool:
    """Whether any of these instructions stores into reg."""
    return bool(re.search(r"^[ \t]*(?:move|const|new|aget|iget|sget|check-cast|instance-of|array-length|neg|not|add|sub|mul"
                          r"|div|rem|and|or|xor|shl|shr|ushr|int-to|long-to|float-to|double-to|filled)[\w/-]* "
                          + re.escape(reg) + r"\b", lines, re.M))


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    rpath = _one([p for p in tree.containing(QUEUE) if any(m.descriptor == "run()V" and QUEUE in m.body for m in methods(tree.get(p)))],
                 "frame read (run() with UsbRequest.queue)")
    text = tree.get(rpath)
    run = next(m for m in methods(text) if m.descriptor == "run()V")
    body_at = text.index("\n", run.start) + 1

    # 1. the frame request: the library's own command, checked to be the transfer UsbQueue sends
    call = _one(list(FRAME_REQUEST_CALL.finditer(run.body)), f"frame request in {tree.rel(rpath)} run()")
    owner, name = call.group(5), call.group(6)
    opath = tree.path_of(owner)
    command = next((m for m in methods(tree.get(opath)) if m.descriptor == f"{name}({CONNECTION}I)I"), None) if opath else None
    if (command is None or "Landroid/hardware/usb/UsbDeviceConnection;->controlTransfer(IIII[BII)I" not in command.body
            or not all(re.search(r"const(?:/4|/16)? " + REG + ", " + c + "$", command.body, re.M) for c in ("0x41", "0x53", "0x3e8"))):
        raise PatchError(f"{NAME}: {owner}->{name}() is not the frame request (control transfer 0x41 / 0x53)")

    # 2. the chunk queue: the request from the frame's request array, the buffer from the frame's chunk
    q = _one(list(QUEUE_CALL.finditer(run.body)), f"chunk queue in {tree.rel(rpath)} run()")
    request = q.group(2)
    before = run.body[:q.start()]
    load = [a for a in re.finditer(r"^[ \t]*aget-object " + re.escape(request) + r", (" + REG + "), (" + REG + r")$", before, re.M)]
    if not load:
        raise PatchError(f"{NAME}: the chunk request in {tree.rel(rpath)} run() does not come from an array")
    load = load[-1]
    requests, index = load.group(1), load.group(2)
    between = before[load.end():]
    chunk = _one(list(re.finditer(r"^[ \t]*invoke-virtual \{(" + REG + r"), " + re.escape(index) + r"\}, (L[\w/$]+;)->[\w$]+\(I\)\[B$",
                                  between, re.M)), f"chunk buffer call before the queue in {tree.rel(rpath)} run()")
    frame, frame_class = chunk.group(1), chunk.group(2)
    if _writes(between, requests) or _writes(between, frame):
        raise PatchError(f"{NAME}: {tree.rel(rpath)} run() changes {requests} or {frame} before the queue")
    regs = [request, q.group(3), q.group(4), requests, frame, call.group(2), call.group(3), call.group(4), "p0"]
    if max(register_number(r, run.body) for r in regs) > 15:
        raise PatchError(f"{NAME}: {tree.rel(rpath)} run() uses registers above v15 for the calls")

    fpath = tree.path_of(frame_class)
    if not fpath:
        raise PatchError(f"{NAME}: no frame buffer class {frame_class}")
    ftext = tree.get(fpath)
    field = _one(re.findall(r"^\.field [^\n]*?([\w$]+):\[\[B$", ftext, re.M), f"chunk array field in {tree.rel(fpath)}")
    sup = re.search(r"^\.super [^\n]*\n", ftext, re.M)

    edits = [(call, f"{call.group(1)}{MARK}: the same request, skipped when the last frame already asked for this one\n"
                    f"{call.group(1)}invoke-static {{{call.group(2)}, {call.group(3)}, {call.group(4)}, p0}}, "
                    f"{QUEUE_HELPER}->frameRequest(Ljava/lang/Object;{CONNECTION}ILjava/lang/Object;)I"),
             (q, f"{q.group(1)}{MARK}: the first chunk queues every chunk of the frame\n"
                 f"{q.group(1)}invoke-static {{{request}, {q.group(3)}, {q.group(4)}, {requests}, {frame}}}, "
                 f"{QUEUE_HELPER}->queue({REQUEST}Ljava/nio/ByteBuffer;I[{REQUEST}Ljava/lang/Object;)Z")]
    for m, new in sorted(edits, key=lambda e: -e[0].start()):
        text = text[:body_at + m.start()] + new + text[body_at + m.end():]
    tree.set(rpath, text)

    ftext = (ftext[:sup.end()] + f".implements {FRAME}\n" + ftext[sup.end():]).rstrip("\n") + f"""

.method public seekpatchChunks()[[B
    .locals 1

    {MARK}: the chunk arrays, for queueing every chunk at once
    iget-object v0, p0, {frame_class}->{field}:[[B

    return-object v0
.end method
"""
    tree.set(fpath, ftext)

    # 3. after the library's requestWait(): the last chunk asks for the next frame
    wpath = _one(tree.containing(REQUEST_WAIT), "class with requestWait()")
    wtext = tree.get(wpath)
    wait = _one(list(WAIT_CALL.finditer(wtext)), f"requestWait() with its result in {tree.rel(wpath)}")
    tree.set(wpath, wtext[:wait.end()] + f"\n{wait.group(1)}{MARK}: the frame's last chunk asks for the next frame\n"
             f"{wait.group(1)}invoke-static {{{wait.group(2)}}}, {QUEUE_HELPER}->arrived({REQUEST})V\n" + wtext[wait.end():])

    add_helpers(tree, "UsbQueue")
    return [f"{tree.rel(rpath)} run(): frame request {owner}->{name}() -> UsbQueue.frameRequest, "
            "UsbRequest.queue -> UsbQueue.queue (every chunk at once)",
            f"{tree.rel(fpath)}: seekpatchChunks() ({field})",
            f"{tree.rel(wpath)}: UsbQueue.arrived() after requestWait() (the next frame requested with the last chunk)"]
