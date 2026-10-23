"""png_photos: save photos as lossless PNG.

The app can already do it -- Settings -> "Save Uncompressed" (preference lossless_comp_key) -- but
hides the switch: it only appears after tapping About -> "Image Processing Software" five times.
Left off, photos are JPEG at quality 100 with 4:2:0 chroma (Android's JPEG encoder has no 4:4:4).
The patch turns the setting on, for both places the app takes it from:

    the preference reader   static (Context)Z around getBoolean("lossless_comp_key"): the share
                            copy and the app's start-up read it
    the photo flag setter   the camera's (Z)V setter of the boolean the photo method checks before
                            choosing PNG; the settings screen calls it directly on a change

on Android 11+ only: the app writes EXIF into every photo, and ExifInterface can only write it into
a PNG since Android 11 -- before, saving the photo fails.  Older Android keeps the setting as is.
"""
from __future__ import annotations

import re

from ..smali import GAP, REG, PatchError, SmaliTree, code_start, methods
from .base import Options, ensure_unpatched, mark

NAME = "png_photos"
SUMMARY = 'save photos as lossless PNG (the app\'s hidden "Save Uncompressed" setting, forced on)'
VERSIONS = "2.1.2 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
KEY = '"lossless_comp_key"'
GET_BOOLEAN = "Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z"
PNG = "Landroid/graphics/Bitmap$CompressFormat;->PNG:Landroid/graphics/Bitmap$CompressFormat;"
ANDROID_11 = 30


def _forced_true(body: str, value_reg: str, note: str, then: str) -> str:
    """Before the first instruction: on Android 11+, value_reg = true and `then`.  Uses v0 and v1
    (the caller makes room); value_reg keeps its value on older Android."""
    at = code_start(body)
    hook = (f"    {MARK}: {note}\n"
            f"    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I\n"
            f"    const/16 v1, 0x{ANDROID_11:x}\n"
            f"    if-lt v0, v1, :seekpatch_stock\n"
            f"    const/4 {value_reg}, 0x1\n"
            f"{then}"
            f"    :seekpatch_stock\n\n")
    return body[:at] + hook + body[at:]


def _with_locals(body: str, n: int) -> str:
    return re.sub(r"^([ \t]*)\.locals (\d+)$", lambda m: f"{m.group(1)}.locals {max(n, int(m.group(2)))}", body,
                  count=1, flags=re.M)


def _reader(tree: SmaliTree) -> str:
    found = [(p, m) for p in tree.containing(KEY, GET_BOOLEAN) for m in methods(tree.get(p))
             if KEY in m.body and GET_BOOLEAN in m.body and m.descriptor.endswith("(Landroid/content/Context;)Z")
             and "static" in m.header.split()]
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one static (Context)Z reader of lossless_comp_key, found {len(found)}")
    path, m = found[0]
    body = _with_locals(m.body, 2)
    body = _forced_true(body, "v0", '"Save Uncompressed" reads as on', "    return v0\n")
    tree.replace_method_body(path, m, body)
    return f"{tree.rel(path)} {m.name}()"


def _setter(tree: SmaliTree) -> str:
    # The photo method picks the file extension on a boolean field: flag ? ".png" : ".jpg".
    photo = [(p, m) for p in tree.containing('"_thermal"', PNG) for m in methods(tree.get(p))
             if '"_thermal"' in m.body and PNG in m.body]
    if len(photo) != 1:
        raise PatchError(f'{NAME}: expected one photo method ("_thermal" + PNG), found {len(photo)}')
    path, m = photo[0]
    flags = set(re.findall(r"iget-boolean (" + REG + r"), p0, (L[\w/$]+;->[\w$]+:Z)" + GAP + r"if-eqz \1, :\w+"
                           + GAP + r'const-string ' + REG + r', "\.png"', m.body))
    flags = {f for _, f in flags}
    if len(flags) != 1:
        raise PatchError(f'{NAME}: expected one flag ? ".png" : ".jpg" in {m.name}(), found {len(flags)}')
    text = tree.get(path)
    setters = [s for s in methods(text) if s.descriptor.endswith("(Z)V")
               and re.fullmatch(r"\s*\.locals 0\s+(?:\.line \d+\s+)*iput-boolean p1, p0, (L[\w/$]+;->[\w$]+:Z)\s+"
                                r"(?:\.line \d+\s+)*return-void\s*", s.body)]
    setters = [s for s in setters if re.search(r"iput-boolean p1, p0, (\S+)", s.body).group(1) in flags]
    if len(setters) != 1:
        raise PatchError(f"{NAME}: expected one (Z)V setter of the photo method's PNG flag in {tree.rel(path)}, "
                         f"found {len(setters)}")
    s = setters[0]
    body = _with_locals(s.body, 2)
    body = _forced_true(body, "p1", "photos are PNG", "")
    tree.replace_method_body(path, s, body)
    return f"{tree.rel(path)} {s.name}()"


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    reader = _reader(tree)
    setter = _setter(tree)
    return [f"Android 11+: preference reader {reader} and photo flag setter {setter} -> PNG"]
