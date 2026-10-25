"""photo_1x: save each photo's thermal frame at the sensor's resolution, too (a setting, off by default).

The photo method gets the colorized frame as a sensor-sized bitmap (320x240 on a Compact Pro, no
overlays), draws it scaled up into the 1280x960 photo canvas, adds the overlays, and writes the
file through a second method that sets the EXIF tags and copies it to its final name.  The patch:

    photo method entry      hands the frame bitmap (and the camera's Context) to
                            seekpatch.Photo1x.capture, before anything scales it
    EXIF + copy method end  calls seekpatch.Photo1x.saved(final file, the app's EXIF orientation)

which writes the frame as PNG, turned upright, next to the photo, under its name with "_thermal"
turned into "_1x" (img_thermal_123.png -> img_1x_123.png): Seek's gallery lists only paths matching
"%Seek Thermal/%_thermal%", so it skips the copy.  Thermal+ photos store the thermal frame.

Settings -> Image & Video gets "Also save a 1x PNG" (seekpatch.PhotoSettings, settings.py), off by
default; where the release has no settings screen, the frame is saved with every photo.  Sources:
helpers/java/seekpatch/{Photo1x,PhotoSettings}.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, code_start, methods, param_registers, register_number
from .base import Options, ensure_unpatched, mark
from .settings import optional_settings

NAME = "photo_1x"
SUMMARY = "a setting to save each photo's thermal frame at the sensor's resolution too (PNG, img_1x_... next to it)"
VERSIONS = "2.1.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
HELPER = "Lseekpatch/Photo1x;"
BITMAP = "Landroid/graphics/Bitmap;"
CONTEXT = "Landroid/content/Context;"
EXIF_SAVE = "Landroid/media/ExifInterface;->saveAttributes()V"
FILE2 = "(Ljava/io/File;Ljava/io/File;Ljava/lang/String;Ljava/lang/String;)V"


def _photo_method(tree: SmaliTree):
    found = [(p, m) for p in tree.containing('"_thermal"', '"deleteme"') for m in methods(tree.get(p))
             if '"_thermal"' in m.body and '"deleteme"' in m.body]
    if len(found) != 1:
        raise PatchError(f'{NAME}: expected one photo method ("_thermal" + "deleteme"), found {len(found)}')
    path, m = found[0]
    sig = m.descriptor[m.descriptor.index("("):]
    regs = param_registers(m)
    types = re.findall(r"\[*(?:L[^;]+;|[ZBSCIJFD])", sig[1:sig.index(")")])
    bitmaps = [r for r, t in zip(regs, types) if t == BITMAP]
    if len(bitmaps) != 1 or "static" in m.header.split():
        raise PatchError(f"{NAME}: photo method {m.name}{sig} does not take one Bitmap")
    contexts = set(re.findall(r"iget-object " + REG + r", p0, (L[\w/$]+;->[\w$]+:" + re.escape(CONTEXT) + ")", m.body))
    if len(contexts) != 1:
        raise PatchError(f"{NAME}: expected the photo method to read one Context field, found {len(contexts)}")
    return path, m, bitmaps[0], contexts.pop()


def _exif_method(tree: SmaliTree, path: str):
    found = [m for m in methods(tree.get(path)) if m.descriptor.endswith(FILE2) and EXIF_SAVE in m.body
             and '"Orientation"' in m.body and "static" not in m.header.split()]
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one (File, File, String, String) EXIF method next to the photo method, "
                         f"found {len(found)}")
    m = found[0]
    orientation = set(re.findall(r"invoke-static \{\}, (L[\w/$]+;->[\w$]+\(\)I)", m.body))
    if len(orientation) != 1:
        raise PatchError(f"{NAME}: expected one orientation call in {m.name}(), found {len(orientation)}")
    if m.body.count("return-void") != 1:
        raise PatchError(f"{NAME}: {m.name}() has more than one return")
    return m, orientation.pop()


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    path, photo, bitmap, context = _photo_method(tree)
    exif, orientation = _exif_method(tree, path)
    if register_number(bitmap, photo.body) > 15 or register_number("p2", exif.body) > 15:
        raise PatchError(f"{NAME}: parameter registers beyond v15")

    at = code_start(photo.body)
    hook = (f"    {MARK}: the sensor-sized frame, before it is scaled up\n"
            f"    iget-object v0, p0, {context}\n"
            f"    invoke-static {{v0, {bitmap}}}, {HELPER}->capture({CONTEXT}{BITMAP})V\n\n")
    tree.replace_method_body(path, photo, photo.body[:at] + hook + photo.body[at:])

    exif = next(m for m in methods(tree.get(path)) if m.body == exif.body)
    done = (f"    {MARK}: the photo is written; the frame goes next to it\n"
            f"    invoke-static {{}}, {orientation}\n"
            f"    move-result v0\n"
            f"    invoke-static {{p2, v0}}, {HELPER}->saved(Ljava/io/File;I)V\n\n")
    tree.replace_method_body(path, exif, re.sub(r"^([ \t]*)return-void$", lambda r: done + r.group(0), exif.body,
                                                count=1, flags=re.M))
    add_helpers(tree, "Photo1x")
    return [f"{tree.rel(path)}: {photo.name}() hands over its frame, {exif.name}() saves it after the photo",
            *optional_settings(tree, NAME, "PhotoSettings", "Also save a 1x PNG")]
