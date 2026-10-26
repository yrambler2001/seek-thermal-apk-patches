"""default_palette: the camera starts in the Tyrian palette instead of Spectra.

The app keeps the chosen palette in its preferences as "color_palette", an index into the palette
list it builds in code ({"White", "Black", "Spectra", "Prism", "Tyrian", "Iron", ...}), and reads
it with a default of 2 -- Spectra -- until a palette is picked.  The patch changes that default to
Tyrian's index, taken from the list itself.  A palette picked before is stored and stays.
"""
from __future__ import annotations

import re

from ..smali import GAP, REG, PatchError, SmaliTree, methods
from .base import ensure_unpatched, mark

NAME = "default_palette"
SUMMARY = "the camera starts in the Tyrian palette instead of Spectra, until another is picked"
VERSIONS = "2.0 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
PALETTE = "Tyrian"
GET_INT = "Landroid/content/SharedPreferences;->getInt(Ljava/lang/String;I)I"


def _palette_index(tree: SmaliTree) -> int:
    """PALETTE's index in the palette list (the String[] its name goes into, with "White"), built either
    with an aput-object per name or with one filled-new-array over the names' registers."""
    found = set()
    for p in tree.containing(f'"{PALETTE}"', '"White"', '"Spectra"'):
        for m in methods(tree.get(p)):
            name = re.search(r"const-string (" + REG + f'), "{PALETTE}"\n', m.body)
            if not name or '"White"' not in m.body:
                continue
            reg, after = name.group(1), m.body[name.end():]
            store = re.match(r"[ \t\n]*(?:\.line \d+\s*)*(?:const(?:/4|/16)? (" + REG + r"), (-?0x[0-9a-f]+)" + GAP
                             + r")?aput-object " + re.escape(reg) + ", " + REG + r", (" + REG + ")", after)
            if store:
                index_reg = store.group(3)
                if store.group(1) == index_reg:
                    found.add(int(store.group(2), 16))
                    continue
                consts = re.findall(r"const(?:/4|/16)? " + re.escape(index_reg) + r", (-?0x[0-9a-f]+)\n",
                                    m.body[:name.start()])
                if consts:
                    found.add(int(consts[-1], 16))
                continue
            array = re.search(r"filled-new-array(/range)? \{([^}]*)\}, \[Ljava/lang/String;", after)
            if not array:
                continue
            if array.group(1):
                first, last = (int(r[1:]) for r in re.findall(REG, array.group(2)))
                if reg[0] == "v" and first <= int(reg[1:]) <= last:
                    found.add(int(reg[1:]) - first)
            elif reg in re.findall(REG, array.group(2)):
                found.add(re.findall(REG, array.group(2)).index(reg))
    if len(found) != 1:
        raise PatchError(f'{NAME}: expected one palette list with "{PALETTE}", found {len(found)}')
    return found.pop()


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    index = _palette_index(tree)
    read = re.compile(r'const-string (' + REG + r'), "color_palette"' + GAP + r"const(?:/4|/16)? (" + REG
                      + r"), (0x[0-9a-f]+)(" + GAP + r"invoke-interface \{" + REG + r", \1, \2\}, " + re.escape(GET_INT) + ")")
    sites = [(p, m, r) for p in tree.containing('"color_palette"', GET_INT) for m in methods(tree.get(p))
             for r in read.finditer(m.body)]
    if len(sites) != 1:
        raise PatchError(f'{NAME}: expected one read of "color_palette" with a default, found {len(sites)}')
    path, m, r = sites[0]
    line_start = m.body.rfind("\n", 0, r.start(2)) + 1
    indent = re.match(r"[ \t]*", m.body[line_start:]).group(0)
    new = (f"{MARK}: {PALETTE} (palette {index}) until one is picked, not {int(r.group(3), 16)}\n"
           f"{indent}const/16 {r.group(2)}, {index:#x}")
    body = m.body[:line_start] + indent + new + m.body[m.body.index("\n", r.start(2)):]
    tree.replace_method_body(path, m, body)
    return [f"{tree.rel(path)} {m.name}(): color_palette defaults to {index} ({PALETTE}) instead of "
            f"{int(r.group(3), 16)}"]
