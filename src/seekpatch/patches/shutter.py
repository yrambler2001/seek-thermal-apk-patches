"""shutter: a "Shutter" button that stops the camera's automatic shutter, and starts it again.

The camera closes its shutter by itself to recalibrate, every few seconds (the Compact: about every 5 s,
more often just after connecting).  Each time it clicks, the picture freezes for 0.44 s and then jumps a
little.
Off, none of that happens, but nothing corrects the sensor's drift: the picture slowly gets noisier and
the readings wander.  On again, the camera shutters right away (its next one is overdue).

The command is the camera firmware's own shutter request: USB vendor request 55 with {255, 253} to
suspend the automatic shutter and {255, 252} to resume it (the Compact's firmware 1.3.0.0 sets and
clears a RAM flag its shutter schedule checks; Seek's later SDK sends the same).  The app never sends
it; the patch sends it only once the button has been tapped.

The patch adds:
    a button below the camera screen's top bar   seekpatch.Shutter.attach, after setContentView (right
                                                  side, below Lock range)
    a call where the app asks for each frame     Shutter.transfer(connection): sends a tap's command on
                                                  that thread, just before the frame request

Versions: the request that asks the camera for a frame looks the same in every release; whether the
camera takes the shutter request is up to its firmware (the button says when it does not).
Sources: helpers/java/seekpatch/Shutter.java; see docs/shutter.md.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, class_descriptor, code_start, methods
from .base import Options, ensure_unpatched, mark
from .seek import camera_activity

NAME = "shutter"
SUMMARY = 'a "Shutter" button: stop the camera\'s automatic shutter (no clicks, no frozen frames), and start it again'
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
SHUTTER = "Lseekpatch/Shutter;"
CONNECTION = "Landroid/hardware/usb/UsbDeviceConnection;"
CONTROL = CONNECTION + "->controlTransfer(IIII[BII)I"
START_GET_IMAGE_TRANSFER = 0x53  # the camera's request for one frame


def _frame_request(tree: SmaliTree) -> str:
    """Shutter.transfer at the top of the method that asks the camera for each frame:
    controlTransfer(0x41, 0x53, 0, 0, {count, 4 bytes}, 4, timeout), the connection in p1."""
    want = re.compile(r"^[ \t]*const/16 " + REG + f", {START_GET_IMAGE_TRANSFER:#x}\n", re.M)
    sites = [(p, m) for p in tree.containing(CONTROL) for m in methods(tree.get(p))
             if m.descriptor.endswith(f"({CONNECTION}I)I") and CONTROL in m.body and want.search(m.body)]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one method asking the camera for a frame (request {START_GET_IMAGE_TRANSFER:#x}), "
                         f"found {len(sites)}")
    path, m = sites[0]
    if "static" in m.header.split():
        raise PatchError(f"{NAME}: the frame request is static, so its connection is not p1")
    text = tree.get(path)
    at = text.index("\n", m.start) + 1 + code_start(m.body)
    indent = re.match(r"[ \t]*", text[at:]).group(0)
    hook = (f"{indent}{MARK}: a tap's shutter command, before the frame request\n"
            f"{indent}invoke-static {{p1}}, {SHUTTER}->transfer({CONNECTION})V\n\n")
    tree.set(path, text[:at] + hook + text[at:])
    return f"{tree.rel(path)} {m.name}()"


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    activity_path, after_layout = camera_activity(tree, NAME)
    activity = class_descriptor(tree.get(activity_path))
    request = _frame_request(tree)

    text = tree.get(activity_path)
    indent = re.match(r"[ \t]*", text[text.rfind("\n", 0, after_layout - 1) + 1:]).group(0)
    hook = (f"\n{indent}{MARK}: the Shutter button, below the top bar\n"
            f"{indent}invoke-static {{p0}}, {SHUTTER}->attach(Landroid/app/Activity;)V\n")
    tree.set(activity_path, text[:after_layout] + hook + text[after_layout:])

    add_helpers(tree, "Shutter", "Floating")
    return [f"{request}: Shutter.transfer before the frame request",
            f"{tree.rel(activity_path)}: the button after {activity.split('/')[-1][:-1]}.setContentView"]
