"""rotation: turn the thermal picture by 90, 180 or 270 degrees, and / or mirror it, from Settings.

Settings -> Image & Video gets "Image rotation" (off, 90°, 180°, 270° clockwise) and "Mirroring" (off,
horizontally, vertically, both; after the turn, as seen on screen), both off by default
(seekpatch.RotationSettings, settings.py).  Only the thermal picture turns.  What the app draws over
it -- the hottest / coldest / spot markers with their temperatures, the temperature bar, the
frame-rate and date box -- stays where it is and upright, and each marker moves with its point of the
picture.  Live view, videos and photos look the same.

The app draws the live view in one shader: the thermal texture and an overlay texture (the markers,
the bar, the text, drawn on a 1280x960 canvas each frame) share one texture coordinate, which the app
itself turns by 180 degrees when the phone is upside down.  The patch:

    vertex shader       a second coordinate for the thermal texture only, thermalCoord: the app's,
                        through uniform mat2 thermalTurn (frame -> picture, minus the identity; zero,
                        the uniform's initial value, changes nothing).  The app's coordinate, which
                        the overlay and Thermal+'s split line use, is left alone.
    fragment shader     the thermal texture sampled at thermalCoord, black where that leaves the
                        texture: a picture turned sideways no longer fits the 4:3 frame and is shrunk
                        to 3/4, to fit its width
    before glDrawArrays seekpatch.Rotation.uniform(): thermalTurn for the settings (live view, video)
    marker method       the (canvas, x, y, ..., icon, text) method that draws a marker and its
                        temperature: x, y first moved to where that point of the picture is now
    photo method        around each drawBitmap of the frame onto the photo canvas: the canvas cleared to
                        black and turned the same way (Rotation.photo / drawn).  Where the app draws a
                        band of the frame (16:9), the whole frame is turned and the canvas crops it, as
                        the live view does.
    photo_1x            its copy is turned too: seekpatch.Photo1x finds seekpatch.Rotation by name

The settings are the patch's only switch, so it needs the Image & Video settings screen (2.0 on).
Run after sharp_scaling, whose shader edits it keeps (patches are applied in the order of
patches/__init__.py).  Sources: helpers/java/seekpatch/{Rotation,RotationSettings}.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import (
    REG,
    PatchError,
    SmaliTree,
    class_descriptor,
    code_start,
    const_strings,
    locals_count,
    methods,
    register_number,
)
from .base import ensure_unpatched, mark
from .settings import install

NAME = "rotation"
SUMMARY = "Image rotation (90°, 180°, 270°) and Mirroring in Settings: the thermal picture turns, the markers stay upright"
VERSIONS = "2.0 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
HELPER = "Lseekpatch/Rotation;"
DRAW_ARRAYS = "Landroid/opengl/GLES20;->glDrawArrays(III)V"
CANVAS = "Landroid/graphics/Canvas;"
RECT = "Landroid/graphics/Rect;"
BITMAP = "Landroid/graphics/Bitmap;"
DRAW_ARGS = f"{BITMAP}{RECT}{RECT}Landroid/graphics/Paint;"
DRAWS = (f"{CANVAS}->drawBitmap({DRAW_ARGS})V",  # the app's
         f"Lseekpatch/SharpScale;->draw({CANVAS}{DRAW_ARGS})V")  # after sharp_scaling
MARKER_SIG = f"({CANVAS}FFFF{BITMAP}Ljava/lang/String;)V"

TURN = "tx = rotTex(imgRotation,tx);\\n"  # the app's own turn of the texture coordinate
UNIFORM = "uniform float imgRotation;\\n"
COORD = "vTextureCoord = (uTexMatrix * vec4(tx.x,tx.y,0.0,1.0)).xy;\\n"  # tx by now zoomed and centred
SAMPLE = re.compile(r"texture2D\(thermalTexture, (sharpCoord\()?vTextureCoord(\)?)\)")
THRM = re.compile(r"vec3 thrm = texture2D\(thermalTexture, [^;\"]*;\\n")
VARYING = re.compile(r"varying (SHARP_P )?vec2 vTextureCoord;\\n")


def _shaders(tree: SmaliTree) -> tuple[str, list[tuple[int, int, str]]]:
    progs = tree.containing("rotTex(imgRotation,tx)", "uniform sampler2D thermalTexture;")
    if len(progs) != 1:
        raise PatchError(f"{NAME}: expected one class with the thermal shaders (rotTex(imgRotation,tx)), found {len(progs)}")
    path = progs[0]
    strings = list(const_strings(tree.get(path)))
    vert = [s for s in strings if TURN in s.group(1)]
    frag = [s for s in strings if "uniform sampler2D thermalTexture;" in s.group(1) and "gl_FragColor" in s.group(1)]
    if len(vert) != 1:
        raise PatchError(f"{NAME}: expected one vertex shader that turns the texture coordinate, found {len(vert)}")
    v = vert[0].group(1)
    if v.count(TURN) != 1 or v.count(UNIFORM) != 1 or v.count(COORD) != 1:
        raise PatchError(f"{NAME}: the vertex shader in {tree.rel(path)} has an unexpected shape")
    v = v.replace(UNIFORM, UNIFORM + "uniform mat2 thermalTurn;\\nvarying vec2 thermalCoord;\\n", 1)
    v = v.replace(COORD, COORD + "thermalCoord = (uTexMatrix * vec4(tx + thermalTurn * (tx - vec2(0.5)), 0.0, 1.0)).xy;\\n", 1)
    edits = [(vert[0].start(1), vert[0].end(1), v)]
    if not frag:
        raise PatchError(f"{NAME}: no thermal fragment shader in {tree.rel(path)}")
    for s in frag:
        g = s.group(1)
        varying = list(VARYING.finditer(g))
        if len(SAMPLE.findall(g)) != 1 or len(THRM.findall(g)) != 1 or len(varying) != 1:
            raise PatchError(f"{NAME}: a thermal fragment shader in {tree.rel(path)} has an unexpected shape")
        decl = varying[0]  # with sharp_scaling's precision (highp), where it ran
        g = g[:decl.end()] + f"varying {decl.group(1) or ''}vec2 thermalCoord;\\n" + g[decl.end():]
        g = SAMPLE.sub(lambda m: m.group(0).replace("vTextureCoord", "thermalCoord"), g, count=1)
        g = THRM.sub(lambda m: m.group(0) + " if (thermalCoord.x < 0.0 || thermalCoord.x > 1.0 || thermalCoord.y < 0.0"
                     " || thermalCoord.y > 1.0) thrm = vec3(0.0);\\n", g, count=1)
        edits.append((s.start(1), s.end(1), g))
    return path, edits


def _hook_draws(text: str) -> tuple[str, int]:
    n = 0

    def hook(m: re.Match) -> str:
        nonlocal n
        n += 1
        return (f"{m.group(1)}{MARK}: thermalTurn for the settings\n"
                f"{m.group(1)}invoke-static {{}}, {HELPER}->uniform()V\n\n{m.group(0)}")

    return re.sub(r"^([ \t]*)invoke-static \{" + REG + ", " + REG + ", " + REG + r"\}, " + re.escape(DRAW_ARRAYS) + "$",
                  hook, text, flags=re.M), n


def _photo(tree: SmaliTree):
    found = [(p, m) for p in tree.containing('"_thermal"', '"deleteme"') for m in methods(tree.get(p))
             if '"_thermal"' in m.body and '"deleteme"' in m.body]
    if len(found) != 1:
        raise PatchError(f'{NAME}: expected one photo method ("_thermal" + "deleteme"), found {len(found)}'
                         " -- 1.9.x saves photos differently")
    path, m = found[0]
    call = re.compile(r"^([ \t]*)invoke-(?:virtual|static) \{(" + REG + "), (" + REG + "), (" + REG + "), (" + REG + "), "
                      + REG + r"\}, (?:" + "|".join(re.escape(d) for d in DRAWS) + r")\n", re.M)
    if not call.search(m.body):
        raise PatchError(f"{NAME}: photo method {m.name}() draws no frame bitmap (drawBitmap with a source and target Rect)")
    return path, m, call


def _marker(tree: SmaliTree, path: str):
    found = [m for m in methods(tree.get(path)) if m.descriptor.endswith(MARKER_SIG) and "static" not in m.header.split()]
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one marker method {MARKER_SIG} next to the photo method, found {len(found)}")
    m = found[0]
    if locals_count(m.body) < 1 or register_number("p3", m.body) > 15:
        raise PatchError(f"{NAME}: the marker method has no v0 to spare, or its registers are beyond v15")
    return m


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    shader_path, edits = _shaders(tree)
    photo_path, photo, call = _photo(tree)
    marker = _marker(tree, photo_path)
    with tree.transaction():  # the settings screen may still be missing: nothing changed then
        return _edit(tree, shader_path, edits, photo_path, photo, call, marker)


def _edit(tree: SmaliTree, shader_path: str, edits, photo_path: str, photo, call: re.Pattern, marker) -> list[str]:
    text = tree.get(shader_path)
    for start, end, g in sorted(edits, reverse=True):
        text = text[:start] + g + text[end:]
    text, n_draw = _hook_draws(text)
    if n_draw == 0:
        raise PatchError(f"{NAME}: no glDrawArrays in {tree.rel(shader_path)}")
    tree.set(shader_path, text)

    n_photo = 0

    def around(c: re.Match) -> str:
        nonlocal n_photo
        n_photo += 1
        indent, canvas, bitmap, src, dst = c.groups()
        return (f"{indent}{MARK}: the photo canvas turned as the live view\n"
                f"{indent}invoke-static {{{canvas}, {bitmap}, {src}, {dst}}}, {HELPER}->photo({CANVAS}{BITMAP}{RECT}{RECT})V\n\n"
                f"{c.group(0)}\n"
                f"{indent}{MARK}: and back\n"
                f"{indent}invoke-static {{{canvas}}}, {HELPER}->drawn({CANVAS})V\n")

    tree.replace_method_body(photo_path, photo, call.sub(around, photo.body))

    marker = next(m for m in methods(tree.get(photo_path)) if m.body == marker.body)
    at = code_start(marker.body)
    hook = (f"    {MARK}: the marker goes where its point of the picture is now\n"
            f"    invoke-static {{p1, p2, p3}}, {HELPER}->markerX({CANVAS}FF)F\n"
            f"    move-result v0\n"
            f"    invoke-static {{p1, p2, p3}}, {HELPER}->markerY({CANVAS}FF)F\n"
            f"    move-result p3\n"
            f"    move p2, v0\n\n")
    tree.replace_method_body(photo_path, marker, marker.body[:at] + hook + marker.body[at:])

    settings = install(tree, NAME)
    add_helpers(tree, "Rotation", "RotationSettings")
    cls = class_descriptor(tree.get(photo_path)).split("/")[-1][:-1]
    return [f"{tree.rel(shader_path)}: the thermal texture through thermalTurn (vertex, {len(edits) - 1} fragment "
            f"shader(s)), set before {n_draw} glDrawArrays",
            f"{cls}.{marker.name}() moves each marker with the picture, {photo.name}() turns {n_photo} photo draw(s)",
            *settings, "settings: Image rotation, Mirroring (seekpatch.RotationSettings)"]
