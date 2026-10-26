"""steady_fps: the live view keeps the camera's frame rate, evenly spaced.

Measured on a Pixel 8 Pro (Android 16) with the Compact (~32 fps), full_fps in: 28 - 30 fps with a
visible stutter, where the camera's own app on an iPhone shows a steady 32.  Three causes:

    screen      nothing says how fast the live view runs, so the system guesses from its frames --
                about 30 a second -- and runs the screen at 30 Hz: about two frames a second are
                dropped and the next one is shown twice as long
    USB thread  the camera library's USB thread is a HandlerThread, whose start resets the library's
                setPriority(10) to normal priority.  Behind the phone camera's HAL threads (the app
                keeps the rear camera open for Thermal+) it waited up to 22 ms for a CPU, the next
                frame request went out too late and the camera skipped a frame, about once a second
    pacing      a frame takes 7 - 23 ms from the camera to the screen, so frames that arrive every
                31 ms are shown 20 - 40 ms apart

The patch (helpers/java/seekpatch/Steady.java):

1. The live view's window asks for the screen's top rate (Surface.setFrameRate, Android 11+), just
   before the render thread makes its EGL surface.  The system gives what it allows: an app with a
   camera open gets at most 60 Hz.
2. Priorities: the USB HandlerThread (onLooperPrepared, added) and the frame loop that queues each
   request (top of its run()) at -19, the render thread (onLooperPrepared) at -10.
3. Pacing: the library's "frame complete" method notes the time; the render thread's draw replaces
   its presentation time (System.nanoTime()) with that time plus a steady delay -- the third slowest
   of the last 32 frames plus 20 ms for the system to put a finished frame on the screen.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, code_start, methods
from .base import ensure_unpatched, mark
from .seek import render_thread

NAME = "steady_fps"
SUMMARY = "steady, evenly spaced live view: the screen's top refresh rate, camera threads first, frame pacing"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
STEADY = "Lseekpatch/Steady;"
HANDLER_THREAD = "Landroid/os/HandlerThread;"
REQUEST_WAIT = "Landroid/hardware/usb/UsbDeviceConnection;->requestWait()"

# Between two instructions: blank lines and debug directives.
GAP = r"(?:[ \t]*(?:\.line \d+|\.local .*|\.end local .*|\.restart local .*)?\n)*"
WINDOW = re.compile(r"^([ \t]*)invoke-direct \{" + REG + ", " + REG + r", (" + REG + r"), " + REG
                    + r"\}, L[\w/$]+;-><init>\(L[\w/$]+;Landroid/view/Surface;Z\)V$", re.M)
PRESENT = re.compile(r"^([ \t]*)invoke-static \{\}, Ljava/lang/System;->nanoTime\(\)J\n" + GAP
                     + r"[ \t]*move-result-wide (" + REG + r")\n(?=" + GAP + r"[ \t]*invoke-virtual \{" + REG
                     + r", \2, " + REG + r"\}, L[\w/$]+;->[\w$]+\(J\)V\n)", re.M)
# The finished-frame method: the buffer's state set to 1, the buffer added to a list, the list notified.
ARRIVED = re.compile(r"const/4 (" + REG + r"), 0x1\n" + GAP + r"(?:[ \t]*:try_start_\d+\n" + GAP + r")?"
                     r"[ \t]*invoke-virtual \{p1, \1\}, L[\w/$]+;->[\w$]+\(I\)V\n")


def _hook(text: str, at: int, call: str, why: str, args: str = "") -> str:
    indent = re.match(r"[ \t]*", text[at:]).group(0)
    return text[:at] + f"{indent}{MARK}: {why}\n{indent}invoke-static {{{args}}}, {STEADY}->{call}\n\n" + text[at:]


def _at_start(tree: SmaliTree, path: str, descriptor: str, call: str, why: str) -> None:
    text = tree.get(path)
    m = next(m for m in methods(text) if m.descriptor == descriptor)
    tree.set(path, _hook(text, text.index("\n", m.start) + 1 + code_start(m.body), call, why))


def _on_looper_prepared(tree: SmaliTree, path: str, call: str, why: str) -> None:
    text = tree.get(path)
    if f".super {HANDLER_THREAD}" not in text:
        raise PatchError(f"{NAME}: {tree.rel(path)} is not a HandlerThread")
    if any(m.name == "onLooperPrepared" for m in methods(text)):
        raise PatchError(f"{NAME}: {tree.rel(path)} already has an onLooperPrepared()")
    tree.set(path, text.rstrip("\n") + f"""

.method protected onLooperPrepared()V
    .locals 0

    {MARK}: {why}
    invoke-static {{}}, {STEADY}->{call}

    return-void
.end method
""")


def _one(found: list, what: str) -> object:
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one {what}, found {len(found)}")
    return found[0]


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    rpath, _ = render_thread(tree, NAME)
    usb = _one(tree.containing('"SeekwareDeviceHandler"'), "SeekwareDeviceHandler class")
    loop = _one([p for p in tree.containing(REQUEST_WAIT) if any(m.descriptor == "run()V" for m in methods(tree.get(p)))],
                "frame loop (requestWait + run())")
    arrived = _one([m.descriptor for m in methods(tree.get(loop)) if m.descriptor.endswith(")V")
                    and "Ljava/util/ArrayList;->add(" in m.body and "Ljava/lang/Object;->notify()V" in m.body
                    and ARRIVED.search(m.body)], f"finished-frame method in {tree.rel(loop)}")

    text = tree.get(rpath)
    window = _one(list(WINDOW.finditer(text)), f"window surface made in {tree.rel(rpath)}")
    text = _hook(text, window.start(), "surface(Landroid/view/Surface;)V",
                 "ask for the screen's top refresh rate", window.group(2))
    present = _one(list(PRESENT.finditer(text)), f"presentation time (System.nanoTime()) in {tree.rel(rpath)}")
    lo = present.group(2)
    hi = f"{lo[0]}{int(lo[1:]) + 1}"
    indent = present.group(1)
    text = (text[:present.end()] + f"\n{indent}{MARK}: the frame's arrival plus a steady delay\n"
            f"{indent}invoke-static {{{lo}, {hi}}}, {STEADY}->present(J)J\n\n{indent}move-result-wide {lo}\n" + text[present.end():])
    tree.set(rpath, text)

    _on_looper_prepared(tree, rpath, "glThread()V", "the live view's GL thread, like Android's own render thread")
    _on_looper_prepared(tree, usb, "usbThread()V", "the camera's USB thread first (HandlerThread resets setPriority)")
    _at_start(tree, loop, "run()V", "frameLoop()V", "the thread that queues each frame request, first")
    _at_start(tree, loop, arrived, "arrived()V", "the time each frame arrives")
    add_helpers(tree, "Steady")
    name = arrived[:arrived.index("(")]
    return [f"{tree.rel(rpath)}: the live view asks for the screen's top refresh rate; frames presented at their"
            " arrival plus a steady delay; GL thread at -10",
            f"{tree.rel(usb)}: the USB thread at -19 (onLooperPrepared)",
            f"{tree.rel(loop)}: the frame loop at -19 (run()), arrival times ({name}())"]
