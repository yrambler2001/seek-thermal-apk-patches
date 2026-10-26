"""default_unit: a new install shows temperatures in Celsius.

The app keeps the temperature unit in its preferences as "units" (0 Fahrenheit, 1 Celsius,
2 Kelvin).  Until one is picked it takes the integer resource default_unit, which is 1 -- except on
a phone set to English (United States), where values-en-rUS makes it 0: Fahrenheit.  The first read
stores that default.  The patch has every getInteger() of that resource answer 1 (seekpatch.Units,
generated here): the unit's default, and the defaults the app derives from it (a threshold of
27 °C rather than 80 °F).  A unit stored before -- picked, or stored on the first start of an
unpatched app -- stays.  Resources are not touched, so this works with `apktool d -r`.
"""
from __future__ import annotations

import re

from ..smali import REG, PatchError, SmaliTree, method_at, methods
from .base import Options, ensure_unpatched, mark

NAME = "default_unit"
SUMMARY = "a new install shows Celsius, also on a phone set to English (US), until another unit is picked"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
CELSIUS = 1
GET_INTEGER = "Landroid/content/res/Resources;->getInteger(I)I"
CALL = re.compile(r"^([ \t]*)invoke-virtual \{(" + REG + "), (" + REG + r")\}, " + re.escape(GET_INTEGER) + "$", re.M)
# the resource id, as a constant (up to 2.3.0) or from the (obfuscated) R class's field (2.3.4)
ID = r"(?:sget (" + REG + r"), (L[\w/$]+;->[\w$]+:I)|const(?:/high16)? (" + REG + r"), (0x7f[0-9a-f]{6}))"
NOT_WRITES = r"(?:if-|[ias]put|monitor-|fill-array-data|packed-switch|sparse-switch|invoke|return|throw|goto)"

UNITS_SMALI = """.class public final Lseekpatch/Units;
.super Ljava/lang/Object;
.source "seek-patch default_unit"

{mark}: the app's default temperature unit, in place of getInteger() of its default_unit resource


# direct methods
.method public static celsius(Landroid/content/res/Resources;I)I
    .locals 1

    const/4 v0, {celsius:#x}

    return v0
.end method
"""


def _id_of(body: str, reg: str) -> str | None:
    """The resource id that last went into reg in body: the R field or the constant."""
    for line in reversed(body.splitlines()):
        s = line.strip()
        if not re.match(r"[\w/-]+ " + reg + ",", s) or re.match(NOT_WRITES, s):
            continue
        m = re.fullmatch(ID, s)
        return (m.group(2) or m.group(4)) if m else None
    return None


def _unit_resource(tree: SmaliTree) -> str:
    """The resource the "units" preference defaults to: the id read with getInteger() where it is read."""
    found = set()
    for path in tree.containing('"units"', GET_INTEGER):
        text = tree.get(path)
        for m in methods(text):
            if not re.search(r'const-string ' + REG + r', "units"\n', m.body):
                continue
            for c in CALL.finditer(m.body):
                rid = _id_of(m.body[:c.start()], c.group(3))
                if rid:
                    found.add(rid)
    if len(found) != 1:
        raise PatchError(f'{NAME}: expected one resource the "units" preference defaults to, found {sorted(found)}')
    return found.pop()


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    rid = _unit_resource(tree)
    sites = []
    for path in tree.containing(rid, GET_INTEGER):
        text = tree.get(path)
        calls = [c for c in CALL.finditer(text)
                 if (m := method_at(text, c.start())) and _id_of(text[m.start:c.start()], c.group(3)) == rid]
        for c in reversed(calls):
            text = (text[:c.start()] + f"{c.group(1)}{MARK}: Celsius until a unit is picked\n"
                    f"{c.group(1)}invoke-static {{{c.group(2)}, {c.group(3)}}}, "
                    "Lseekpatch/Units;->celsius(Landroid/content/res/Resources;I)I" + text[c.end():])
        if calls:
            tree.set(path, text)
            sites.append(f"{tree.rel(path)} ({len(calls)})")
    tree.add_class("Lseekpatch/Units;", UNITS_SMALI.format(mark=MARK, celsius=CELSIUS))
    return [f"default_unit resource {rid}: Celsius at {', '.join(sites)}"]
