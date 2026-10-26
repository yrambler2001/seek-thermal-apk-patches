"""usb_prompt: Android asks once for the camera, not twice.

Seek's camera library (SeekwareLibrary, 1.9.1's names) searches for cameras when the camera
screen is created and again each time it resumes, and each search asks Android for permission
(UsbManager.requestPermission) for every camera it has not opened.  On a fresh start -- the camera
plugged in since the app last ran, so the permission is gone -- the second search comes before the
answer to the first, and Android queues a second dialog.  It shows once the first is answered, over
the live picture, and answering it does nothing.

The patch routes the library's requests through seekpatch.UsbPrompt.requestPermission, which skips
a request while one for the same camera waits for its answer, and has the library's receiver
(onReceive) tell seekpatch.UsbPrompt.heard about each answer and unplug first, which ends the wait.
A camera the app already has permission for is always asked for: Android answers that at once,
without a dialog.  Source of the helper: helpers/java/seekpatch/UsbPrompt.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, class_descriptor, code_start, method_at, methods
from .base import Options, ensure_unpatched, mark

NAME = "usb_prompt"
SUMMARY = "one USB permission dialog for the camera, not a second one that does nothing"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
PERMISSION = '"com.tyriansystems.Seekware.SeekwareLibrary.USB_PERMISSION"'
REQUEST = ("Landroid/hardware/usb/UsbManager;->requestPermission(Landroid/hardware/usb/UsbDevice;"
           "Landroid/app/PendingIntent;)V")
ON_RECEIVE = "onReceive(Landroid/content/Context;Landroid/content/Intent;)V"
CALL = re.compile(r"^([ \t]*)invoke-virtual \{(" + REG + ", " + REG + ", " + REG + r")\}, " + re.escape(REQUEST) + "$",
                  re.M)


def _library(tree: SmaliTree) -> str:
    libs = [p for p in tree.containing(PERMISSION, ON_RECEIVE)
            if re.search(r"^\.super Landroid/content/BroadcastReceiver;$", tree.get(p), re.M)]
    if len(libs) != 1:
        raise PatchError(f"{NAME}: expected one Seekware library receiver (asking for {PERMISSION}), found {len(libs)}")
    return libs[0]


def _answer_source(body: str, reg: str) -> str | None:
    """The instruction that last wrote reg in body (straight-line text before the call)."""
    writes = [w for w in re.findall(r"^[ \t]*([\w/-]+ " + reg + r",[^\n]*)$", body, re.M)
              if not re.match(r"(?:if-|[ias]put|monitor-|fill-array-data|packed-switch|sparse-switch)", w)]
    return writes[-1].strip() if writes else None


def _requests(tree: SmaliTree, cls: str) -> int:
    """Every permission request answered to the library -- its PendingIntent the library's static one --
    through the helper.  The library asks itself, and up to 2.1.7 a thread of its asks too."""
    answer = re.compile(r"sget-object " + REG + ", " + re.escape(cls) + r"->[\w$]+:Landroid/app/PendingIntent;")
    count = 0
    for path in tree.containing(REQUEST):
        own = class_descriptor(tree.get(path))
        text = tree.get(path)
        calls = list(CALL.finditer(text))
        if len(calls) != text.count(REQUEST):
            raise PatchError(f"{NAME}: a permission request in {own} is not a plain three-register call")
        for c in calls:
            m = method_at(text, c.start())
            source = _answer_source(text[m.start:c.start()], c.group(2).split(", ")[2]) if m else None
            if not source or not answer.fullmatch(source):
                raise PatchError(f"{NAME}: {own} asks for USB permission with an answer not addressed to {cls} "
                                 f"({source})")
        for c in reversed(calls):
            text = (text[:c.start()] + f"{c.group(1)}{MARK}: not while the same camera's dialog is waiting\n"
                    f"{c.group(1)}invoke-static {{{c.group(2)}}}, Lseekpatch/UsbPrompt;->requestPermission("
                    "Landroid/hardware/usb/UsbManager;Landroid/hardware/usb/UsbDevice;Landroid/app/PendingIntent;)V"
                    + text[c.end():])
        tree.set(path, text)
        count += len(calls)
    if not count:
        raise PatchError(f"{NAME}: no USB permission request in {cls}")
    return count


def _receiver(tree: SmaliTree, path: str, cls: str) -> None:
    found = [m for m in methods(tree.get(path)) if m.descriptor == ON_RECEIVE and "static" not in m.header.split()]
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one {cls}->{ON_RECEIVE}, found {len(found)}")
    m = found[0]
    at = code_start(m.body)
    tree.replace_method_body(path, m, m.body[:at]
                             + f"    {MARK}: an answer or an unplug ends the wait for that camera's dialog\n"
                             f"    invoke-static {{p2}}, Lseekpatch/UsbPrompt;->heard(Landroid/content/Intent;)V\n\n"
                             + m.body[at:])


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    path = _library(tree)
    cls = class_descriptor(tree.get(path))
    count = _requests(tree, cls)
    _receiver(tree, path, cls)
    add_helpers(tree, "UsbPrompt")
    return [f"{tree.rel(path)}: {count} permission request{'s' if count > 1 else ''} through seekpatch.UsbPrompt, "
            f"one dialog at a time per camera; {ON_RECEIVE.split('(')[0]}() ends the wait"]
