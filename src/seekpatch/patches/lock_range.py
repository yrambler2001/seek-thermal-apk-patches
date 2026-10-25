"""lock_range: a "Lock range" button that holds the colors where they are.

The app's image comes out of libseekip's contrast stage (bclahe_process): every frame it builds a
histogram of the frame's raw values, clips it, averages it with the previous frames' and turns it
into the curve from raw value to palette entry (create_transfer).  So the colors are re-spread over
every frame: a hot object entering the view recolors everything else.  While locked, the stage keeps
the curve of the last frame shown: the image does not change at the tap, and a raw value keeps its
color from then on.

The patch adds:
    lib/<abi>/libseekpatch_lock.so               a hook on libseekip's PLT slot for create_transfer:
                                                  while locked it skips the call, so the curve stays
    a button below the camera screen's top bar   seekpatch.Lock.attach, after setContentView
    a call right after the per-frame feature 900  seekpatch.Lock.frame(): loads and hooks on the first
                                                  tap, then passes taps on; a reconnect unlocks
    a call where each frame's results arrive     Lock.scene(min, max): the scene's extremes (degrees C)
    the temperature bar's span labels            Lock.bar / low / high: while locked, the minimum and
                                                  maximum it showed at the tap

Versions: libseekip calls create_transfer through its PLT from 2.2.3 on (libseekip 2.11.3.2); the
hook also checks at run time that create_transfer has the size of a verified build (arm64-v8a, and
armeabi-v7a of 2.2.3 - 2.3.0 and of 2.3.3 - 2.3.4).  Built for arm64-v8a and armeabi-v7a only.
Sources: helpers/native/lock.c, helpers/java/seekpatch/Lock.java; see docs/lock-range.md.
"""
from __future__ import annotations

import re

from .. import native
from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, class_descriptor, code_start, methods
from .base import Options, ensure_unpatched, mark
from .seek import camera_activity, feature_900_call

NAME = "lock_range"
SUMMARY = 'a "Lock range" button: the colors stay as they are, whatever enters the view'
VERSIONS = "2.2.3 - 2.3.4"
MIN_VERSION_CODE = 276  # 2.2.3
RECOMMENDED = True

MARK = mark(NAME)
LOCK = "Lseekpatch/Lock;"
SEEKIP = "libseekip.so"
RESULTS_SIG = "(IIIIFFF)V"
BAR_SIG = re.compile(r"\(L[\w/$]+;IZLandroid/graphics/Canvas;Landroid/graphics/Rect;\)V$")


def _hook(indent: str, why: str, *lines: str) -> str:
    return f"{indent}{MARK}: {why}\n" + "".join(f"{indent}{line}\n\n" for line in lines)


def _results(tree: SmaliTree) -> str:
    """Lock.scene at the top of the method each frame's thermography results arrive in: (min x, min y,
    max x, max y, min, max, spot), the temperatures in degrees C."""
    sites = [(p, m) for p in tree.containing(RESULTS_SIG) for m in methods(tree.get(p))
             if m.descriptor.endswith(RESULTS_SIG) and "static" not in m.header.split()]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one method taking the frame's results {RESULTS_SIG}, found {len(sites)}")
    path, m = sites[0]
    text = tree.get(path)
    at = text.index("\n", m.start) + 1 + code_start(m.body)
    indent = re.match(r"[ \t]*", text[at:]).group(0)
    hook = _hook(indent, "the scene's minimum and maximum", f"invoke-static/range {{p5 .. p6}}, {LOCK}->scene(FF)V")
    tree.set(path, text[:at] + hook + text[at:])
    return f"{tree.rel(path)} {m.name}()"


def _bar(tree: SmaliTree) -> str:
    """The temperature bar: `if (span) { min = <span min>; max = <span max>; }` writes the labels kept
    at the tap while locked."""
    sites = [(p, m) for p in tree.containing("IZLandroid/graphics/Canvas;Landroid/graphics/Rect;)V")
             for m in methods(tree.get(p)) if BAR_SIG.search(m.descriptor) and "if-eqz p3, :" in m.body]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one temperature bar method, found {len(sites)}")
    path, m = sites[0]
    cls = class_descriptor(tree.get(path))
    body = m.body
    tests = list(re.finditer(r"^([ \t]*)if-eqz p3, :(\w+)\n", body, re.M))
    end = re.search(r"^[ \t]*:" + tests[0].group(2) + r"\n", body[tests[0].end():], re.M) if len(tests) == 1 else None
    if not end:
        raise PatchError(f"{NAME}: the temperature bar's span test changed shape")
    start, stop = tests[0].end(), tests[0].end() + end.start()
    reads = list(re.finditer(r"^([ \t]*)iget (" + REG + "), " + REG + ", " + re.escape(cls) + r"->[\w$]+:F\n",
                             body[start:stop], re.M))
    if len(reads) != 2:
        raise PatchError(f"{NAME}: expected the bar to read the span's minimum and maximum, found {len(reads)} reads")
    for r, which in reversed(list(zip(reads, ("low", "high")))):
        reg = r.group(2)
        at = start + r.end()
        body = body[:at] + "\n" + _hook(r.group(1), f"the {'minimum' if which == 'low' else 'maximum'} kept at the tap",
                                        f"invoke-static/range {{{reg} .. {reg}}}, {LOCK}->{which}(F)F",
                                        f"move-result {reg}") + body[at:]
    at = tests[0].start()
    body = body[:at] + _hook(tests[0].group(1), "while locked the bar writes the labels kept at the tap",
                             f"invoke-static/range {{p3 .. p3}}, {LOCK}->bar(Z)Z", "move-result p3") + body[at:]
    tree.replace_method_body(path, m, body)
    return f"{tree.rel(path)} {m.name}()"


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    code = tree.version_code
    if code is None:
        raise PatchError(f"{NAME}: cannot tell the app version, and the patch is only verified on {VERSIONS}")
    if code < MIN_VERSION_CODE:
        raise PatchError(f"{NAME}: app {tree.identity.get('versionName')} (versionCode {code}) predates the image "
                         f"library the hook is verified on (apps {VERSIONS})")
    abis = [a for a in tree.abis if a in native.ABIS and tree.has_native(a, SEEKIP)]
    if not abis:
        raise PatchError(f"{NAME}: no {SEEKIP} for {' / '.join(native.ABIS)} in the apk "
                         f"(it has native code for: {', '.join(tree.abis) or 'none'})")
    call = feature_900_call(tree, NAME)
    activity_path, after_layout = camera_activity(tree, NAME)
    activity = class_descriptor(tree.get(activity_path))

    text = tree.get(call.path)
    hook = (f"\n{call.indent}{MARK}: a tap's lock / unlock, before the frame is processed\n"
            f"{call.indent}invoke-static {{}}, {LOCK}->frame()V\n")
    tree.set(call.path, text[:call.end] + hook + text[call.end:])
    results = _results(tree)
    bar = _bar(tree)

    text = tree.get(activity_path)
    indent = re.match(r"[ \t]*", text[text.rfind("\n", 0, after_layout - 1) + 1:]).group(0)
    hook = (f"\n{indent}{MARK}: the Lock range button, below the top bar\n"
            f"{indent}invoke-static {{p0}}, {LOCK}->attach(Landroid/app/Activity;)V\n")
    tree.set(activity_path, text[:after_layout] + hook + text[after_layout:])

    for abi in abis:
        tree.add_native_library(abi, native.LOCK, native.library(abi, native.LOCK))
    add_helpers(tree, "Lock")
    others = [a for a in tree.abis if a not in abis]
    return [f"{tree.rel(call.path)}: Lock.frame after the feature-900 call",
            f"{results}: Lock.scene, the scene's minimum and maximum",
            f"{bar}: the temperature bar keeps its labels while locked",
            f"{tree.rel(activity_path)}: the button after {activity.split('/')[-1][:-1]}.setContentView",
            f"lib/{{{','.join(abis)}}}/{native.LOCK}" + (f" (none for {', '.join(others)})" if others else "")]
