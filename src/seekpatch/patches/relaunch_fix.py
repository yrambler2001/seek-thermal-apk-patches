"""relaunch_fix: the camera starts with a picture after the app was killed, not a -40 °C screen.

USB marks the packets of a bulk endpoint DATA0, DATA1, DATA0, ... (the data toggle), so the
receiver can tell a repeated packet from a new one.  When the app's process dies while the camera
streams -- swiped away from the recent apps, force-stopped -- the phone and the camera can be left
one step apart.  At the next start the phone takes the camera's first packet for a repeat and drops
it, without an error: the first 512 bytes of the first frame, its header included.  The camera sends
a frame of type 4 once, first, and the camera library needs it to start its thermography; without it
SeekIPprocess() answers 1407 (a bad header) and every pixel after that reads -40 °C, a flat magenta
in most palettes, until the camera is unplugged.  Measured on a Compact PRO FF (firmware 4.18.2.0)
on a Pixel 8 Pro: 5 of 6 relaunches a second after a force-stop.  The rest of that frame, and every
frame after it, arrive whole.

The patch routes the library's one claimInterface() through seekpatch.Relaunch.claimInterface, which
sets the interface again once it is claimed (UsbDeviceConnection.setInterface).  Linux then resets
the phone's toggles and sends SET_INTERFACE, which resets the camera's -- or, if the camera refuses
it, CLEAR_FEATURE(ENDPOINT_HALT) on each endpoint, which resets them too.  It happens before the
first command, so both ends start at DATA0.  Source of the helper:
helpers/java/seekpatch/Relaunch.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, class_descriptor
from .base import Options, ensure_unpatched, mark

NAME = "relaunch_fix"
SUMMARY = "the camera starts with a picture after the app was swiped away or killed, not a -40 °C magenta screen"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
FAILED = '"claim interface failed"'
CLAIM = "Landroid/hardware/usb/UsbDeviceConnection;->claimInterface(Landroid/hardware/usb/UsbInterface;Z)Z"
CALL = re.compile(r"^([ \t]*)invoke-virtual \{(" + REG + ", " + REG + ", " + REG + r")\}, " + re.escape(CLAIM) + "$", re.M)


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    paths = tree.containing(FAILED, CLAIM)
    if len(paths) != 1:
        raise PatchError(f"{NAME}: expected one USB init class (claimInterface, {FAILED}), found {len(paths)}")
    path = paths[0]
    text = tree.get(path)
    calls = list(CALL.finditer(text))
    if len(calls) != 1 or text.count(CLAIM) != 1:
        raise PatchError(f"{NAME}: expected one plain claimInterface() in {class_descriptor(text)}, "
                         f"found {text.count(CLAIM)}")
    c = calls[0]
    tree.set(path, text[:c.start()] + f"{c.group(1)}{MARK}: the interface set again, the data toggles start at DATA0\n"
             f"{c.group(1)}invoke-static {{{c.group(2)}}}, Lseekpatch/Relaunch;->claimInterface("
             "Landroid/hardware/usb/UsbDeviceConnection;Landroid/hardware/usb/UsbInterface;Z)Z" + text[c.end():])
    add_helpers(tree, "Relaunch")
    return [f"{tree.rel(path)}: claimInterface() through seekpatch.Relaunch, which sets the interface again "
            "(both ends' data toggles back to DATA0)"]
