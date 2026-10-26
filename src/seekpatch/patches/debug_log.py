"""debug_log: send the Seekware SDK's compiled-out debug log to logcat (tag "Seekware").

The SDK logs through a tiny static class (n/a in 2.3.4) whose methods are stripped to return-void
in release builds -- a(String msg) and a two-string variant (tag, msg) -- but the callers are still
there, including the DAQ timing:

    DAQ: fps: <n>                              frames requested from the camera per second
    miliseconds per USB IMG transaction: <n>   frame credit + all bulk chunks
    DAQ: waited: <n> ms to get a frame to render

This patch gives the two methods bodies (Log.d).  Watch with:  adb logcat -s Seekware
The DAQ thread logs ~16 lines per frame: fine for diagnosis, not for daily use.
"""
from __future__ import annotations

import re

from ..smali import REG, PatchError, SmaliTree, methods
from .base import ensure_unpatched, mark

NAME = "debug_log"
SUMMARY = 'send the SDK\'s compiled-out debug log (USB timing, DAQ fps) to logcat, tag "Seekware"'
VERSIONS = "2.0 - 2.3.4"
RECOMMENDED = False

MARK = mark(NAME)
ANCHOR = '"DAQ: awaiting USB copy"'

BODY_MSG = """    .locals 1

    {mark}
    const-string v0, "Seekware"

    invoke-static {{p0}}, Ljava/lang/String;->valueOf(Ljava/lang/Object;)Ljava/lang/String;

    move-result-object p0

    invoke-static {{v0, p0}}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    return-void
"""

BODY_TAG_MSG = """    .locals 0

    {mark}
    invoke-static {{p0}}, Ljava/lang/String;->valueOf(Ljava/lang/Object;)Ljava/lang/String;

    move-result-object p0

    invoke-static {{p1}}, Ljava/lang/String;->valueOf(Ljava/lang/Object;)Ljava/lang/String;

    move-result-object p1

    invoke-static {{p0, p1}}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    return-void
"""


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    # the logger is whatever the DAQ thread hands its constant messages to
    loggers = set()
    for p in tree.containing(ANCHOR):
        for m in re.finditer(r"const-string (" + REG + "), " + re.escape(ANCHOR) + r"\n(?:[ \t]*(?:\.line \d+)?[ \t]*\n)*"
                             r"[ \t]*invoke-static \{\1\}, (L[\w/$]+;)->[\w$]+\(Ljava/lang/String;\)V", tree.get(p)):
            loggers.add(m.group(2))
    if len(loggers) != 1:
        raise PatchError(f"{NAME}: expected one logger class behind {ANCHOR}, found {sorted(loggers)}"
                         " -- not a Seek Thermal 2.0 - 2.3 apk? (1.9.x has no DAQ log)")
    cls = loggers.pop()
    path = tree.path_of(cls)
    if not path:
        raise PatchError(f"{NAME}: {cls} not found")

    done = []
    for sig, body in (("(Ljava/lang/String;)V", BODY_MSG), ("(Ljava/lang/String;Ljava/lang/String;)V", BODY_TAG_MSG)):
        found = [m for m in methods(tree.get(path)) if m.header.startswith("public static ") and m.header.endswith(sig)
                 and re.fullmatch(r"public static [\w$]+" + re.escape(sig), m.header)]
        if len(found) != 1:
            raise PatchError(f"{NAME}: expected one static {sig} method in {cls}, found {len(found)}")
        m = found[0]
        code = [ln.strip() for ln in m.body.splitlines()
                if ln.strip() and not ln.strip().startswith((".line", ".prologue"))]
        if code != [".locals 0", "return-void"]:
            raise PatchError(f"{NAME}: {cls}->{m.descriptor} is not an empty stub: {code}")
        tree.replace_method_body(path, m, body.format(mark=MARK))
        done.append(m.descriptor)
    return [f"logger {cls}: {', '.join(done)} -> Log.d", f"{tree.rel(path)}: watch with  adb logcat -s Seekware"]
