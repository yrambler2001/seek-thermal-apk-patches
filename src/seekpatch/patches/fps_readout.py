"""fps_readout: the live view's frame-rate readout updates every 0.5 s instead of every 3 s.

With Settings -> "Show Frame Rate" on (one of the switches hidden_settings shows), the live view writes
the thermal frame rate in its corner, "27.9 Hz".  The camera thread counts its frames and, once 3000 ms
have passed since the last reading (1000 ms in 2.0.x), sets the rate to frames / seconds: a new number
every 3 s, the average over them.  The patch makes it 500 ms, the average over the last half second.

    the frame counter   a method with currentTimeMillis(): (now - last), as a double, compared with the
                        window (3000.0, or 1000.0), then frames / ((now - last) / 1000.0); the window
                        becomes 500.0 (the 1000.0 the time is divided by stays)

Versions: the readout is in 2.0 - 2.3.4.
"""
from __future__ import annotations

import re

from ..smali import REG, PatchError, SmaliTree, methods
from .base import Options, ensure_unpatched, mark

NAME = "fps_readout"
SUMMARY = 'the "Show Frame Rate" readout (Hz) updates every 0.5 s instead of every 3 s'
VERSIONS = "2.0 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
NOW = "Ljava/lang/System;->currentTimeMillis()J"
WINDOWS = {"0x40a7700000000000L": 3000, "0x408f400000000000L": 1000}  # the doubles 3000.0, 1000.0
SECOND = "0x408f400000000000L"     # 1000.0
HALF_SECOND = "0x407f400000000000L"  # 500.0


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    # (now - last) as a double, then the window constant and, a few instructions on, the comparison
    elapsed = re.compile(r"^[ \t]*sub-long (" + REG + r"), " + REG + ", " + REG + r"\n(?:[ \t]*(?:\.line \d+)?\n)*"
                         r"[ \t]*long-to-double (" + REG + r"), \1\n(?:[ \t]*(?:\.line \d+)?\n)*"
                         r"([ \t]*)const-wide (" + REG + r"), (" + "|".join(WINDOWS) + r")[^\n]*\n"
                         r"(?:.*\n){0,16}?[ \t]*cmp[lg]-double " + REG + r", \2, \4\n", re.M)
    sites = []
    for p in tree.containing(NOW, SECOND):
        for m in methods(tree.get(p)):
            if NOW in m.body and "div-double" in m.body:
                sites += [(p, m, h) for h in elapsed.finditer(m.body)]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one frame counter comparing the elapsed time with 3000.0 or 1000.0 ms, "
                         f"found {len(sites)}")
    path, m, h = sites[0]
    window = WINDOWS[h.group(5)]
    at = h.start(3)
    line_end = m.body.index("\n", at) + 1
    body = (m.body[:at] + f"{h.group(3)}{MARK}: a reading every 500 ms, not {window}\n"
            f"{h.group(3)}const-wide {h.group(4)}, {HALF_SECOND}    # 500.0\n" + m.body[line_end:])
    tree.replace_method_body(path, m, body)
    return [f"{tree.rel(path)} {m.name}(): the frame rate is recomputed every 500 ms instead of {window}"]
