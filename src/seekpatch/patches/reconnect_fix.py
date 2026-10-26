"""reconnect_fix: the camera comes back after the camera screen was closed.

Seek's camera library (SeekwareLibrary, 1.9.1's names) is a process-wide singleton and the
BroadcastReceiver for its USB events: the permission answers it asks for and the camera being
unplugged.  DeviceManager.onDestroy() -- the camera screen (MainActivity) closing -- calls
SeekwareLibrary.unRegisterUSBIntent(), and the process lives on.  Up to 2.1.7, MainActivity.onStart()
registers it again (DeviceManager.onStart() -> reRegisterUSBIntent()).  2.2.0 dropped that: from
then on the receiver is registered only when the singleton is created, so once the camera screen has
closed the app hears neither permission answers nor unplugging, until the process dies.  The screen
closes on Back from the home page, and, from 2.3.0, when the app comes back after the camera was
unplugged in the background (onRestart() finishes it when there is no camera).  From 2.3.0 each
screen has its own DeviceManager, which then gets no camera at all; in 2.2.x the DeviceManager is a
singleton that keeps the camera, and what breaks is the next unplug: unheard, it leaves the camera
listed, so the camera plugged back in (same USB address) is taken for it -- a black live view.

From 2.2.0 the patch empties unRegisterUSBIntent(): the receiver stays registered for as long as the
singleton lives, as it is never registered again.  Up to 2.1.7 it is left as is.

From 2.3.0 the patch also releases a camera the closed screen left open.  On its way out the screen
puts the camera to sleep and stops the library's threads, but leaves it in the library's device
list, so the next screen does not search for a camera and gets none.  When the next screen
registers its notification listener (registerNotifcationListener()), the patch closes each listed
camera as unplugging it does, releases its USB interface and connection, and empties the list; the
library's own search then asks for permission (already granted, so answered at once) and opens the
camera again.

From 2.3.0, the camera screen also stays when it comes back without a camera.  MainActivity's
onRestart() finishes it when the DeviceManager has no camera -- the camera was unplugged while the
app was in the background -- so the tap that brought the app back closes it, and the permission
dialog its last search asked for opens a camera for no screen; only the next tap shows the picture.
The patch drops that finish(): the screen shows *Connect Your Camera*, its search asks for the
camera, and the camera opens in it, as when the camera is plugged in with the app in front.  Up to
2.2.3 the screen finishes only after Back on the app's reminder screen, and is left as is.

A receiver that outlives its screen should hear only its own app.  Every Seek app asks for
permission with the same action, as an implicit broadcast, and registers its receiver exported: the
answer to one app's request reaches every Seek app that is listening, and one that has permission
too opens the camera, in the background, from under the app in front.  The patch addresses the
request's PendingIntent to the app's own package (setPackage), and registers the receiver with
RECEIVER_NOT_EXPORTED on Android 13+, where unplugging (sent by Android) and the app's own answers
(sent as the app) still arrive and another app's answers do not.  Older Android has no such flag;
there the app's own answers still reach only itself.
"""
from __future__ import annotations

import re

from ..smali import GAP, REG, PatchError, SmaliTree, class_descriptor, code_start, methods
from .base import ensure_unpatched, mark

NAME = "reconnect_fix"
SUMMARY = "the camera comes back after the camera screen closed (Back, or unplugging it in the background)"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
PERMISSION = '"com.tyriansystems.Seekware.SeekwareLibrary.USB_PERMISSION"'
UNREGISTER = r"invoke-virtual \{(" + REG + r"), (" + REG + r")\}, Landroid/content/Context;->unregisterReceiver\(Landroid/content/BroadcastReceiver;\)V"
CLASS = r"L[\w/$]+;"

KEEP_BODY = """    .locals 0

    {mark}: the USB receiver stays registered -- nothing registers it again for the next camera screen
    return-void
"""

# unplugging, in the receiver: each listed device that matches is closed, then taken off the list
DEVICE_CLOSE = r"invoke-virtual \{(" + REG + r")\}, (" + CLASS + r")->([\w$]+)\(\)V" + GAP \
    + r"iget-object (" + REG + r"), p0, %(cls)s->([\w$]+):Ljava/util/ArrayList;" + GAP \
    + r"invoke-virtual \{\4, \1\}, Ljava/util/ArrayList;->remove\(Ljava/lang/Object;\)Z"
# ... after the USB wrapper's close(holder) -- interface released, connection closed
WRAPPER_CLOSE = r"iget-object (" + REG + r"), p0, %(cls)s->([\w$]+):(" + CLASS + r")" + GAP \
    + r"invoke-virtual \{\1, " + REG + r"\}, \3->([\w$]+)\((" + CLASS + r")\)I"
# registerNotifcationListener(): the listener is kept, and the search runs if no device is listed
LISTENER = r"iput-object p1, p0, %(cls)s->[\w$]+:" + CLASS + GAP \
    + r"(iget-object (" + REG + r"), p0, %(cls)s->%(devices)s:Ljava/util/ArrayList;" + GAP \
    + r"invoke-virtual \{\2\}, Ljava/util/ArrayList;->size\(\)I" + GAP + r"move-result \2" + GAP \
    + r"if-nez \2, :\w+" + GAP + r"invoke-direct \{p0\}, %(cls)s->[\w$]+\(\)V)"

RELEASE_CALL = """{mark}: a camera the last camera screen left open is released first
    invoke-direct {{p0}}, {cls}->seekpatch_release()V

    """

RELEASE = """
{mark}: each listed camera -- asleep, its threads stopped by the screen that closed -- is closed as on
{mark}: unplugging, and its USB interface and connection released, so that the search opens it again
.method private seekpatch_release()V
    .locals 3

    iget-object v0, p0, {cls}->{devices}:Ljava/util/ArrayList;

    :seekpatch_next
    invoke-virtual {{v0}}, Ljava/util/ArrayList;->isEmpty()Z

    move-result v1

    if-nez v1, :seekpatch_done

    const/4 v1, 0x0

    invoke-virtual {{v0, v1}}, Ljava/util/ArrayList;->remove(I)Ljava/lang/Object;

    move-result-object v1

    check-cast v1, {device}

    :seekpatch_try_start
    invoke-virtual {{v1}}, {device}->{close}()V

    iget-object v2, p0, {cls}->{wrapper}:{wrapper_cls}

    invoke-virtual {{v1}}, {device}->{holder}(){holder_cls}

    move-result-object v1

    invoke-virtual {{v2, v1}}, {wrapper_cls}->{release}({holder_cls})I
    :seekpatch_try_end
    .catch Ljava/lang/Exception; {{:seekpatch_try_start .. :seekpatch_try_end}} :seekpatch_next

    goto :seekpatch_next

    :seekpatch_done
    return-void
.end method
"""

# the permission request's PendingIntent, and the receiver's registration (2.3.1+: with flags on Android 13+)
BROADCAST = re.compile(r"invoke-static \{(" + REG + r"), " + REG + r", (" + REG + r"), " + REG + r"\}, "
                       r"Landroid/app/PendingIntent;->getBroadcast\(Landroid/content/Context;ILandroid/content/Intent;I\)"
                       r"Landroid/app/PendingIntent;")
REGISTER = re.compile(
    r"invoke-virtual \{(" + REG + r"), (" + REG + r"), (" + REG + r")\}, Landroid/content/Context;->registerReceiver"
    r"\(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;\)Landroid/content/Intent;"
    r"|invoke-static \{(" + REG + r"), (" + REG + r"), (" + REG + r"), " + REG + r"\}, " + CLASS + r"->[\w$]+"
    r"\(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I\)Landroid/content/Intent;")

OWN_CALL = """{mark}: the answer is addressed to this app, not to every Seek app's receiver
    invoke-static {{{intent}, {context}}}, {cls}->seekpatch_own(Landroid/content/Intent;Landroid/content/Context;)V

    """
REGISTER_CALL = """{mark}: registered so that on Android 13+ it hears this app and Android only
    invoke-static {{{context}, {receiver}, {filter}}}, {cls}->seekpatch_register(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;"""

ISOLATE = """
{mark}: the permission request's answer goes to this app only: every Seek app listens for the same action
.method private static seekpatch_own(Landroid/content/Intent;Landroid/content/Context;)V
    .locals 1

    invoke-virtual {{p1}}, Landroid/content/Context;->getPackageName()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {{p0, v0}}, Landroid/content/Intent;->setPackage(Ljava/lang/String;)Landroid/content/Intent;

    return-void
.end method

{mark}: not exported on Android 13+ (RECEIVER_NOT_EXPORTED): unplugging (from Android) and this app's own
{mark}: permission answers still arrive, another Seek app's answers do not
.method private static seekpatch_register(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;
    .locals 2

    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x21

    if-lt v0, v1, :seekpatch_old

    const/4 v0, 0x4

    invoke-virtual {{p0, p1, p2, v0}}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;

    move-result-object v0

    return-object v0

    :seekpatch_old
    invoke-virtual {{p0, p1, p2}}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;

    move-result-object v0

    return-object v0
.end method
"""


def _library(tree: SmaliTree) -> str:
    libs = [p for p in tree.containing(PERMISSION, "unregisterReceiver")
            if re.search(r"^\.super Landroid/content/BroadcastReceiver;$", tree.get(p), re.M)]
    if len(libs) != 1:
        raise PatchError(f"{NAME}: expected one Seekware library receiver (asking for {PERMISSION}), found {len(libs)}")
    return libs[0]


def _keep_receiver(tree: SmaliTree, path: str, cls: str) -> str:
    text = tree.get(path)
    singletons = re.findall(r"^\.field [^\n]*\bstatic ([\w$]+):" + re.escape(cls) + "$", text, re.M)
    if len(singletons) != 1:
        raise PatchError(f"{NAME}: expected one static {cls} (the library) in {cls}, found {len(singletons)}")
    singleton = singletons[0]
    unregs = [m for m in methods(text) if re.search(UNREGISTER, m.body)]
    if len(unregs) != 1:
        raise PatchError(f"{NAME}: expected one method of {cls} to unregister a receiver, found {len(unregs)}")
    unreg = unregs[0]
    call = re.search(UNREGISTER, unreg.body)
    if ("static" not in unreg.header.split() or not unreg.descriptor.endswith(")V")
            or not re.search(r"sget-object " + call.group(2) + ", " + re.escape(cls) + "->" + re.escape(singleton) + ":",
                             unreg.body)):
        raise PatchError(f"{NAME}: {cls}->{unreg.descriptor} does not unregister the library ({singleton})")
    # up to 2.1.7 the camera screen registers the library again when it starts (reRegisterUSBIntent())
    again = [m.descriptor for m in methods(text)
             if "static" in m.header.split() and "Landroid/content/Context;->registerReceiver(" in m.body
             and any(p != path for p in tree.containing(f"{cls}->{m.descriptor}"))]
    if again:
        return (f"{tree.rel(path)} {unreg.descriptor}: left as is -- the app registers the receiver again "
                f"({again[0]}) whenever a camera screen starts")
    tree.replace_method_body(path, unreg, KEEP_BODY.format(mark=MARK))
    return f"{tree.rel(path)} {unreg.descriptor}: the USB receiver stays registered"


def _release_left_open(tree: SmaliTree, path: str, cls: str) -> str:
    text = tree.get(path)
    c = re.escape(cls)
    closes = re.findall(DEVICE_CLOSE % {"cls": c}, text)
    if not closes:
        return (f"{tree.rel(path)}: no camera to release: up to 2.2.3 the DeviceManager lives as long as the "
                "process and keeps its camera for the next screen")
    if len(closes) != 1:
        raise PatchError(f"{NAME}: expected one device close in {cls}'s unplug handling, found {len(closes)}")
    _, device, close, _, devices = closes[0]
    # the USB wrapper's close(holder): a method of the wrapper that releases the interface and closes the connection
    wrappers = set()
    for _, wrapper, wrapper_cls, release, holder_cls in re.findall(WRAPPER_CLOSE % {"cls": c}, text):
        body = next((m.body for m in methods(tree.get(tree.path_of(wrapper_cls) or ""))
                     if m.descriptor == f"{release}({holder_cls})I"), "")
        if ("Landroid/hardware/usb/UsbDeviceConnection;->releaseInterface(" in body
                and "Landroid/hardware/usb/UsbDeviceConnection;->close()V" in body):
            wrappers.add((wrapper, wrapper_cls, release, holder_cls))
    if len(wrappers) != 1:
        raise PatchError(f"{NAME}: expected {cls} to close devices through one USB wrapper method that releases the "
                         f"interface and closes the connection, found {len(wrappers)}")
    wrapper, wrapper_cls, release, holder_cls = wrappers.pop()
    holders = set(re.findall(r"invoke-virtual \{" + REG + r"\}, " + re.escape(device) + r"->([\w$]+)\(\)"
                             + re.escape(holder_cls), text))
    if len(holders) != 1:
        raise PatchError(f"{NAME}: expected {cls} to get one {holder_cls} from {device}, found {sorted(holders)}")
    holder = holders.pop()
    listeners = list(re.finditer(LISTENER % {"cls": c, "devices": re.escape(devices)}, text))
    if len(listeners) != 1:
        raise PatchError(f"{NAME}: expected one listener registration in {cls} that searches when no device is "
                         f"listed, found {len(listeners)}")
    at = listeners[0].start(1)
    text = text[:at] + RELEASE_CALL.format(mark=MARK, cls=cls) + text[at:]
    text = text.rstrip("\n") + "\n" + RELEASE.format(mark=MARK, cls=cls, devices=devices, device=device, close=close,
                                                    wrapper=wrapper, wrapper_cls=wrapper_cls, holder=holder,
                                                    holder_cls=holder_cls, release=release)
    tree.set(path, text)
    return (f"{tree.rel(path)}: cameras left open by the last camera screen (list {devices}) are closed "
            f"({device}->{close}), released ({wrapper_cls}->{release}) and opened again when the next one registers")


def _isolate(tree: SmaliTree, path: str, cls: str) -> str:
    text = tree.get(path)
    requests = list(BROADCAST.finditer(text))
    if not requests:
        raise PatchError(f"{NAME}: expected {cls} to make the permission request's PendingIntent, found none")
    for m in requests:
        if PERMISSION not in next(x.body for x in methods(text) if x.start < m.start() < x.end):
            raise PatchError(f"{NAME}: {cls} makes a PendingIntent in a method without {PERMISSION}")
    registrations = list(REGISTER.finditer(text))
    if not registrations:
        raise PatchError(f"{NAME}: expected {cls} to register its receiver, found no registration")
    edits = [(m.start(), m.start(), OWN_CALL.format(mark=MARK, cls=cls, intent=m.group(2), context=m.group(1)))
             for m in requests]
    for m in registrations:
        context, receiver, filt = m.group(1, 2, 3) if m.group(1) else m.group(4, 5, 6)
        edits.append((m.start(), m.end(), REGISTER_CALL.format(mark=MARK, cls=cls, context=context, receiver=receiver,
                                                               filter=filt)))
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    tree.set(path, text.rstrip("\n") + "\n" + ISOLATE.format(mark=MARK))
    return (f"{tree.rel(path)}: the permission answer is addressed to this app, and on Android 13+ the receiver "
            f"hears no other app (PendingIntents: {len(requests)}, registrations: {len(registrations)})")


# onRestart(), 2.3.0+: the screen finishes when the DeviceManager's "has a camera" says no
RESTART_FINISH = (r"[ \t]*invoke-static \{\}, (" + CLASS + r")->([\w$]+)\(\)Z" + GAP + r"move-result (" + REG + ")" + GAP
                  + r"if-nez \3, (:\w+)" + GAP + r"invoke-virtual \{p0\}, " + CLASS + r"->finish\(\)V" + GAP + r"\4\n")
STAY = """{mark}: the screen stays without a camera: its search asks for the one plugged in, which opens in it
    nop
"""


def _has_camera(tree: SmaliTree, cls: str, name: str) -> bool:
    """Is cls->name()Z a static "is the field set?" check of one of cls's own static fields?"""
    path = tree.path_of(cls)
    m = next((m for m in methods(tree.get(path)) if m.descriptor == f"{name}()Z"), None) if path else None
    if not m or "static" not in m.header.split():
        return False
    field = re.search(r"sget-object (" + REG + "), " + re.escape(cls) + r"->[\w$]+:" + CLASS, m.body)
    return bool(field and re.search(r"if-(?:eq|ne)z " + field.group(1) + ",", m.body))


def _stay_open(tree: SmaliTree) -> str:
    found = []
    for path in tree.containing("onRestart()V", "->finish()V"):
        for m in methods(tree.get(path)):
            if m.descriptor != "onRestart()V":
                continue
            at = code_start(m.body)
            hit = re.match(RESTART_FINISH, m.body[at:])
            if hit and _has_camera(tree, hit.group(1), hit.group(2)):
                found.append((path, m, at, hit))
    if not found:
        return ("no camera screen that closes itself without a camera: up to 2.2.3 it does so only after Back on "
                "the reminder screen")
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one onRestart() that finishes without a camera, found {len(found)}")
    path, m, at, hit = found[0]
    finish = re.search(r"^[ \t]*invoke-virtual \{p0\}, " + CLASS + r"->finish\(\)V\n", m.body[at:at + hit.end()], re.M)
    start, end = at + finish.start(), at + finish.end()
    tree.replace_method_body(path, m, m.body[:start] + "    " + STAY.format(mark=MARK) + m.body[end:])
    return (f"{tree.rel(path)} onRestart(): stays open without a camera ({hit.group(1)}->{hit.group(2)}() no "
            "longer finishes it)")


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    path = _library(tree)
    cls = class_descriptor(tree.get(path))
    return [_keep_receiver(tree, path, cls), _release_left_open(tree, path, cls), _isolate(tree, path, cls),
            _stay_open(tree)]
