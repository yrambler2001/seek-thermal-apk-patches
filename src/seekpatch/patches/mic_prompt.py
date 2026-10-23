"""mic_prompt: ask for the microphone when a video starts -- and only then.

On Android 11+ the app's photo, video and gallery buttons all go through one method that first
checks RECORD_AUDIO; without it the method requests the permission and returns, and the activity
has no onRequestPermissionsResult, so the tap is lost.  After two denials Android stops showing
the dialog, and from then on none of the three can start.  The patch:

    the permission check    seekpatch.Mic.gate(activity, action, recording): photos, the gallery
                            and stopping a recording go ahead; starting a video without the
                            microphone asks for it
    the permission request  seekpatch.Mic.request: Android's dialog -- or, once Android no longer
                            shows it, a dialog offering the app's settings or recording without sound
    onRequestPermissionsResult (added to the activity)
                            seekpatch.Mic.onResult: remember to start the video, with sound if allowed
    after the thermal upload
                            seekpatch.Mic.frame: start it -- the dialog pauses the app, which stops
                            the camera, so the video waits for the first frame after it runs again

The recording flag is the boolean the video button's start/stop toggle tests.  Source of the
helper: helpers/java/seekpatch/Mic.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import GAP, REG, PatchError, SmaliTree, class_descriptor, methods, register_number
from .base import Options, ensure_unpatched, mark
from .seek import render_thread, upload_call

NAME = "mic_prompt"
SUMMARY = "ask for the microphone when a video starts; photos and the gallery never need it"
VERSIONS = "2.3.3 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
RECORD_AUDIO = '"android.permission.RECORD_AUDIO"'
CHECK = "checkSelfPermission(Ljava/lang/String;)I"
REQUEST = "requestPermissions([Ljava/lang/String;I)V"
ON_RESULT = "onRequestPermissionsResult(I[Ljava/lang/String;[I)V"
VIDEO_ACTION = 1  # seekpatch.Mic.ACTION_VIDEO

OVERRIDE = """
{mark}: seekpatch.Mic starts the video the microphone question interrupted
.method public {on_result}
    .locals 2

    invoke-super {{p0, p1, p2, p3}}, {super_cls}->{on_result}

    invoke-static {{p0, p1, p2, p3}}, Lseekpatch/Mic;->onResult(Landroid/app/Activity;I[Ljava/lang/String;[I)Z
    move-result v0
    if-eqz v0, :seekpatch_done

    # back to video mode (the dialog's pause put the app in photo mode), then start
    const/4 v1, {video_mode}
    {switch_invoke} {{p0, v1}}, {cls}->{switch}

    const-string v0, "android.permission.WRITE_EXTERNAL_STORAGE"
    const/4 v1, 0x{video:x}
    {invoke} {{p0, v0, v1}}, {cls}->{action}

    :seekpatch_done
    return-void
.end method
"""


def _calls_to(tree: SmaliTree, cls: str, api: str) -> str:
    """Regex for a call of `api` on the activity: invoke-virtual, or a static outline (d8 moves
    API calls newer than minSdk into helpers like o/r.a(MainActivity, String)) whose body calls it."""
    outlines = []
    for p in tree.containing("->" + api):
        for m in methods(tree.get(p)):
            if "static" in m.header.split() and m.descriptor.startswith(m.name + "(" + cls) and "->" + api in m.body:
                outlines.append(re.escape(class_descriptor(tree.get(p)) + "->" + m.descriptor))
    virtual = r"invoke-virtual \{p0, " + REG + r"(?:, " + REG + r")?\}, L[\w/$]+;->" + re.escape(api)
    static = r"invoke-static \{p0, " + REG + r"(?:, " + REG + r")?\}, (?:" + "|".join(outlines) + ")" if outlines else None
    return "(?:" + virtual + (")" if not static else "|" + static + ")")


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    hits = []
    for p in tree.containing(RECORD_AUDIO):
        text = tree.get(p)
        cls = class_descriptor(text)
        for m in methods(text):
            if m.descriptor.endswith("(Ljava/lang/String;I)V") and RECORD_AUDIO in m.body and "sput-boolean" in m.body:
                hits.append((p, cls, m))
    if len(hits) != 1:
        raise PatchError(f"{NAME}: expected one (String, int) media-action method that checks RECORD_AUDIO, "
                         f"found {len(hits)}")
    path, cls, y = hits[0]
    text = tree.get(path)
    if ON_RESULT in text:
        raise PatchError(f"{NAME}: {cls} already has onRequestPermissionsResult")
    super_cls = re.search(r"^\.super (L[\w/$]+;)$", text, re.M).group(1)

    # The first check: check(RECORD_AUDIO) -> if granted skip, else request and return.
    check = re.search(r"^([ \t]*)(" + _calls_to(tree, cls, CHECK) + r")" + GAP + r"move-result (" + REG + r")"
                      + GAP + r"if-eqz \3, :\w+" + GAP + "(" + _calls_to(tree, cls, REQUEST) + ")" + GAP + "return-void",
                      y.body, re.M)
    if not check:
        raise PatchError(f"{NAME}: no check-request-return of RECORD_AUDIO in {y.name}()")
    string_reg = re.search(r"\{p0, (" + REG + r")", check.group(2)).group(1)
    if string_reg != check.group(3):
        raise PatchError(f"{NAME}: the permission string register {string_reg} outlives the check")

    # The video action: `if-ne p2, <1>, ...` then a no-argument toggle on a boolean field (start / stop).
    toggles = set(re.findall(r"if-ne p2, (" + REG + r"), :\w+" + GAP + r"invoke-direct \{p0\}, " + re.escape(cls)
                             + r"->([\w$]+)\(\)V", y.body))
    flags = set()
    for reg, name in toggles:
        if not re.search(r"const/4 " + reg + ", 0x" + str(VIDEO_ACTION) + r"\n", y.body):
            continue
        for m in methods(text):
            if m.descriptor == name + "()V":
                f = re.match(r"\s*\.locals \d+\s+(?:\.line \d+\s+)*iget-boolean (" + REG + r"), p0, (" + re.escape(cls)
                             + r"->[\w$]+:Z)\s+(?:\.line \d+\s+)*if-(?:eqz|nez) \1, :\w+", m.body)
                if f:
                    flags.add(f.group(2))
    if len(flags) != 1:
        raise PatchError(f"{NAME}: expected one start/stop toggle for action {VIDEO_ACTION} in {y.name}(), "
                         f"found {len(flags)}")
    flag = flags.pop()
    if max(register_number(r, y.body) for r in ("p0", "p2", string_reg)) > 15:
        raise PatchError(f"{NAME}: registers beyond v15 in {y.name}()")

    ind = check.group(1)
    hook = (f"{ind}{MARK}: microphone only for starting a video (seekpatch.Mic)\n"
            f"{ind}iget-boolean {string_reg}, p0, {flag}\n"
            f"{ind}invoke-static {{p0, p2, {string_reg}}}, Lseekpatch/Mic;->gate(Landroid/app/Activity;IZ)I")
    request_regs = re.search(r"\{([^}]*)\}", check.group(4)).group(1)
    if len(request_regs.split(",")) != 3:
        raise PatchError(f"{NAME}: unexpected permission request {check.group(4)}")
    body = (y.body[:check.start()] + hook + y.body[check.start() + len(check.group(1)) + len(check.group(2)):check.start(4)]
            + f"invoke-static {{{request_regs}}}, Lseekpatch/Mic;->request(Landroid/app/Activity;[Ljava/lang/String;I)V"
            + y.body[check.end(4):])
    tree.replace_method_body(path, y, body)

    # The photo / video mode switch and the video mode's number: what swiping left calls in photo mode.
    swipe = [m for m in methods(text) if '"onSwipeLeft Mode:"' in m.body]
    switch = re.findall(r"const/4 (" + REG + r"), (0x[0-9a-f]+)" + GAP + r"(invoke-direct|invoke-virtual) \{p0, \1\}, "
                        + re.escape(cls) + r"->([\w$]+\(I\)V)", swipe[0].body) if len(swipe) == 1 else []
    if len(switch) != 1:
        raise PatchError(f"{NAME}: expected one mode switch in the swipe-left handler, found {len(switch)}")
    _, video_mode, switch_invoke, switch_method = switch[0]

    invoke = "invoke-direct" if y.is_private else "invoke-virtual"
    tree.set(path, tree.get(path).rstrip("\n") + "\n" + OVERRIDE.format(
        mark=MARK, on_result=ON_RESULT, super_cls=super_cls, cls=cls, action=y.descriptor, invoke=invoke,
        video=VIDEO_ACTION, video_mode=video_mode, switch_invoke=switch_invoke, switch=switch_method))

    rpath, rcls = render_thread(tree, NAME)
    site_path, site = upload_call(tree, rpath, rcls, NAME)
    t = tree.get(site_path)
    tree.set(site_path, t[:site.end()] + f"\n{site.group(1)}{MARK}: a video the microphone question held back starts now\n"
             f"{site.group(1)}invoke-static {{}}, Lseekpatch/Mic;->frame()V\n" + t[site.end():])
    add_helpers(tree, "Mic")
    return [f"{tree.rel(path)}: {y.name}() asks only for videos (recording flag {flag.split('->')[1]}), "
            f"onRequestPermissionsResult + the first thermal frame after it start them ({tree.rel(site_path)})"]
