"""resume_fix: no crash when the app comes back from a dialog.

When the app pauses, the live view's GL thread is stopped: it drops its window surface (sets the
field to null) without destroying the EGL surface.  Going home destroys the view's window anyway,
but a translucent activity on top -- Android's permission dialog, which the app shows for the
microphone -- leaves it alive.  On resume the new GL thread cannot connect to the still-connected
window (eglCreateWindowSurface: "already connected", EGL_BAD_ALLOC) and its first draw throws
"draw start: glError 0x506", which kills the app.

The patch calls seekpatch.Egl.releaseWindow() right before that drop: on the GL thread, it makes no
surface current and destroys the current one.  Source: helpers/java/seekpatch/Egl.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import GAP, REG, PatchError, SmaliTree, methods
from .base import ensure_unpatched, mark
from .seek import render_thread

NAME = "resume_fix"
SUMMARY = "no crash on returning from a dialog (permission prompt) over the live view"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    rpath, cls = render_thread(tree, NAME)
    c = re.escape(cls)
    # The window surface field: set from new <WindowSurface>(core, Surface, boolean).
    fields = set(re.findall(r"invoke-direct \{(" + REG + r"), " + REG + ", " + REG + ", " + REG + r"\}, (L[\w/$]+;)-><init>\(L[\w/$]+;"
                            r"Landroid/view/Surface;Z\)V" + GAP + r"iput-object \1, p0, " + c + r"->([\w$]+):\2", tree.get(rpath)))
    fields = {(f, t) for _, t, f in fields}
    if len(fields) != 1:
        raise PatchError(f"{NAME}: expected one window-surface field in {tree.rel(rpath)}, found {len(fields)}")
    field, wtype = fields.pop()
    drop = re.compile(r"^([ \t]*)const/4 (" + REG + r"), 0x0" + GAP + r"iput-object \2, " + REG + ", " + c + "->"
                      + re.escape(field) + ":" + re.escape(wtype) + "$", re.M)
    sites = [(p, m, d) for p in tree.containing(cls) for m in methods(tree.get(p)) for d in drop.finditer(m.body)]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one place that drops the window surface, found {len(sites)}")
    path, m, d = sites[0]
    hook = (f"{d.group(1)}{MARK}: destroy the EGL surface, so the next GL thread can use the window\n"
            f"{d.group(1)}invoke-static {{}}, Lseekpatch/Egl;->releaseWindow()V\n\n")
    tree.replace_method_body(path, m, m.body[:d.start()] + hook + m.body[d.start():])
    add_helpers(tree, "Egl")
    return [f"{tree.rel(path)} {m.name}(): releases the window ({field}) before dropping it"]
