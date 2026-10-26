"""sharp_scaling: scale the thermal image up like the iOS app does.

The colorized frame is sensor-sized (206x156 on the Compact) and Android blows it up with plain
bilinear filtering -- the thermal texture has GL_LINEAR magnification and the saved photo is drawn
with a FILTER_BITMAP_FLAG Paint -- so every pixel is blended into its neighbour across its whole
width, which reads as a soft image.  Seek's iOS app holds each pixel for its first and last
quarter and blends only across the middle half: the kernel of a 2x nearest-neighbour upscale
followed by bilinear.  (Measured: see docs/sharp-scaling.md.)

    live view + video   on the GPU.  The thermal fragment shader remaps the sample position inside
                        each texel ("sharp bilinear"), so the hardware bilinear filter blends over
                        1/sharpness texel.  The shader needs the texture size: the upload method
                        records it and a uniform `thermalSize` is set before each draw, with the
                        sharpness (`thermalSharp`).  Texture
                        coordinates move to highp -- mediump is fp16 on Mali and would quantize the
                        remap to ~0.1 texel; GPUs without fragment highp (optional in GLES 2.0:
                        Mali-400/450, early Tegra) keep the stock bilinear sample.
    saved photo         the photo method draws a 2x nearest-upscaled copy of the frame bitmap with
                        the same filtered Paint (CPU, once per capture).

    settings            where the release has the settings screen (settings.py), Settings -> Image &
                        Video gets "Upscaling" (seekpatch.Upscale): Smooth (stock), Sharp 1.5 - 8 or
                        Blocky.  It starts at Sharp 2; it sets the shader's uniform
                        thermalSharp (1 or less returns the coordinate unchanged: the exact stock
                        bilinear sample; Blocky is 1000) and the photo's nearest factor (1: the stock
                        draw; 0, Blocky: the frame drawn with an unfiltered copy of the Paint).

Image processing and temperatures are untouched.
"""
from __future__ import annotations

import re

from ..smali import REG, PatchError, SmaliTree, const_strings, methods
from .base import ensure_unpatched, mark
from .seek import GL_TEX_IMAGE, render_thread, texture_upload
from .settings import optional_settings

NAME = "sharp_scaling"
SUMMARY = "iOS-like upscaling: blend over half a pixel instead of a whole one (GPU shader)"
VERSIONS = "2.0 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
HELPER = "Lseekpatch/SharpScale;"
DRAW_ARRAYS = "Landroid/opengl/GLES20;->glDrawArrays(III)V"
DRAW_BITMAP = ("Landroid/graphics/Canvas;->drawBitmap(Landroid/graphics/Bitmap;Landroid/graphics/Rect;"
               "Landroid/graphics/Rect;Landroid/graphics/Paint;)V")
SAMPLE = "texture2D(thermalTexture, vTextureCoord)"
SHARPNESS = 2.0   # the shader's blend width at the start, 1/2 of a texel: the iOS kernel
PHOTO_FACTOR = 2  # the photo's nearest upscale at the start, the same kernel on the CPU

GLSL_DEFS = """#ifdef GL_FRAGMENT_PRECISION_HIGH
#define SHARP_P highp
#else
#define SHARP_P mediump
#define SHARP_OFF
#endif
"""
GLSL_FUNC = """uniform SHARP_P vec2 thermalSize;
uniform SHARP_P float thermalSharp;
SHARP_P vec2 sharpCoord(SHARP_P vec2 c)
{
#ifdef SHARP_OFF
 return c;
#else
 if (thermalSize.x < 1.0 || thermalSharp <= 1.0) return c;
 SHARP_P vec2 t = c * thermalSize - 0.5;
 SHARP_P vec2 i = floor(t);
 SHARP_P vec2 f = clamp((t - i - 0.5) * thermalSharp + 0.5, 0.0, 1.0);
 return (i + f + 0.5) / thermalSize;
#endif
}
"""

HELPER_SMALI = """.class public final Lseekpatch/SharpScale;
.super Ljava/lang/Object;
.source "seek-thermal-apk-patches sharp_scaling"

{mark}: thermal texture size and sharpness for the sharp-bilinear shader; nearest photo upscale


# static fields
.field private static h:I

.field private static w:I

# the shader's blend width, 1/sharpness of a texel (<= 1: the stock bilinear sample); Sharp 2 at the
# start, changed at run time by seekpatch.Upscale (the settings)
.field public static sharpness:F = {sharpness}

# the photo's nearest upscale before the filtered draw (1: the stock draw; 0: drawn unfiltered, square
# pixels)
.field public static photoFactor:I = {k}


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {{p0}}, Ljava/lang/Object;-><init>()V

    return-void
.end method

# right before the thermal glTexImage2D: remember the texture size
.method public static size(II)V
    .locals 0

    sput p0, Lseekpatch/SharpScale;->w:I

    sput p1, Lseekpatch/SharpScale;->h:I

    return-void
.end method

# right before glDrawArrays (program in use): thermalSize = texture size and thermalSharp =
# sharpness, if the program has them.  Looked up on every call, no cache: the video encoder may draw
# from another thread.
.method public static uniform()V
    .locals 4

    const/4 v0, 0x1
    new-array v0, v0, [I
    const v1, 0x8b8d
    const/4 v2, 0x0
    invoke-static {{v1, v0, v2}}, Landroid/opengl/GLES20;->glGetIntegerv(I[II)V
    aget v1, v0, v2
    if-eqz v1, :done

    const-string v0, "thermalSize"
    invoke-static {{v1, v0}}, Landroid/opengl/GLES20;->glGetUniformLocation(ILjava/lang/String;)I
    move-result v0
    if-ltz v0, :done

    sget v1, Lseekpatch/SharpScale;->w:I
    int-to-float v1, v1
    sget v2, Lseekpatch/SharpScale;->h:I
    int-to-float v2, v2
    invoke-static {{v0, v1, v2}}, Landroid/opengl/GLES20;->glUniform2f(IFF)V

    const/4 v0, 0x1
    new-array v0, v0, [I
    const v1, 0x8b8d
    const/4 v2, 0x0
    invoke-static {{v1, v0, v2}}, Landroid/opengl/GLES20;->glGetIntegerv(I[II)V
    aget v1, v0, v2
    const-string v0, "thermalSharp"
    invoke-static {{v1, v0}}, Landroid/opengl/GLES20;->glGetUniformLocation(ILjava/lang/String;)I
    move-result v0
    if-ltz v0, :done

    sget v1, Lseekpatch/SharpScale;->sharpness:F
    invoke-static {{v0, v1}}, Landroid/opengl/GLES20;->glUniform1f(IF)V

    :done
    return-void
.end method

# Canvas.drawBitmap(bitmap, src, dst, paint) with the bitmap photoFactor x nearest-upscaled first, or
# (photoFactor 0) with a copy of the paint that does not filter
.method public static draw(Landroid/graphics/Canvas;Landroid/graphics/Bitmap;Landroid/graphics/Rect;Landroid/graphics/Rect;Landroid/graphics/Paint;)V
    .locals 6

    sget v5, Lseekpatch/SharpScale;->photoFactor:I
    if-nez v5, :factor
    if-eqz p4, :draw
    new-instance v0, Landroid/graphics/Paint;
    invoke-direct {{v0, p4}}, Landroid/graphics/Paint;-><init>(Landroid/graphics/Paint;)V
    const/4 v1, 0x0
    invoke-virtual {{v0, v1}}, Landroid/graphics/Paint;->setFilterBitmap(Z)V
    move-object p4, v0
    goto :draw

    :factor
    const/4 v0, 0x1
    if-le v5, v0, :draw

    invoke-virtual {{p1}}, Landroid/graphics/Bitmap;->getWidth()I
    move-result v0
    mul-int v0, v0, v5
    invoke-virtual {{p1}}, Landroid/graphics/Bitmap;->getHeight()I
    move-result v1
    mul-int v1, v1, v5
    const/4 v2, 0x0
    invoke-static {{p1, v0, v1, v2}}, Landroid/graphics/Bitmap;->createScaledBitmap(Landroid/graphics/Bitmap;IIZ)Landroid/graphics/Bitmap;
    move-result-object p1

    if-eqz p2, :draw
    iget v0, p2, Landroid/graphics/Rect;->left:I
    mul-int v0, v0, v5
    iget v1, p2, Landroid/graphics/Rect;->top:I
    mul-int v1, v1, v5
    iget v2, p2, Landroid/graphics/Rect;->right:I
    mul-int v2, v2, v5
    iget v3, p2, Landroid/graphics/Rect;->bottom:I
    mul-int v3, v3, v5
    new-instance v4, Landroid/graphics/Rect;
    invoke-direct {{v4, v0, v1, v2, v3}}, Landroid/graphics/Rect;-><init>(IIII)V
    move-object p2, v4

    :draw
    invoke-virtual {{p0, p1, p2, p3, p4}}, {draw}
    return-void
.end method
"""


def _esc(glsl: str) -> str:
    """GLSL inserted into a smali string literal: newlines as \\n (the shaders hold no quotes)."""
    return glsl.replace("\n", "\\n")


def _patch_shaders(tree: SmaliTree) -> tuple[str, int, int]:
    progs = tree.containing("uniform sampler2D thermalTexture;", SAMPLE)
    if len(progs) != 1:
        raise PatchError(f"{NAME}: expected one class with the thermal fragment shader, found {len(progs)}")
    path = progs[0]
    text = tree.get(path)
    strings = list(const_strings(text))
    frag = [s for s in strings if "uniform sampler2D thermalTexture;" in s.group(1) and SAMPLE in s.group(1)]
    vert = [s for s in strings if "gl_Position" in s.group(1) and "vTextureCoord" in s.group(1)]
    if not frag:
        raise PatchError(f"{NAME}: no single string in {tree.rel(path)} holds the thermal fragment shader")
    if len(vert) != 1:
        raise PatchError(f"{NAME}: expected one thermal vertex shader, found {len(vert)}")
    edits = []
    for s in frag:
        g = s.group(1)
        if (g.count(SAMPLE) != 1 or g.count("void main()") != 1 or "varying vec2 vTextureCoord;\\n" not in g
                or "precision " not in g):
            raise PatchError(f"{NAME}: thermal fragment shader in {tree.rel(path)} has an unexpected shape")
        first_precision = g.index("precision ")
        g = g[:first_precision] + _esc(GLSL_DEFS) + g[first_precision:]
        g = g.replace("varying vec2 vTextureCoord;\\n", "varying SHARP_P vec2 vTextureCoord;\\n", 1)
        g = g.replace("void main()", _esc(GLSL_FUNC) + "void main()", 1)
        g = g.replace(SAMPLE, "texture2D(thermalTexture, sharpCoord(vTextureCoord))", 1)
        edits.append((s.start(1), s.end(1), g))
    v = vert[0].group(1)
    if "precision mediump float;" in v:
        edits.append((vert[0].start(1), vert[0].end(1), v.replace("precision mediump float;", "precision highp float;", 1)))
    for start, end, g in sorted(edits, reverse=True):
        text = text[:start] + g + text[end:]

    n_draw = 0

    def hook(m: re.Match) -> str:
        nonlocal n_draw
        n_draw += 1
        return (f"{m.group(1)}{MARK}: thermalSize for the sharp-bilinear shader\n"
                f"{m.group(1)}invoke-static {{}}, {HELPER}->uniform()V\n\n{m.group(0)}")

    text = re.sub(r"^([ \t]*)invoke-static \{" + REG + ", " + REG + ", " + REG + r"\}, " + re.escape(DRAW_ARRAYS) + "$",
                  hook, text, flags=re.M)
    if n_draw == 0:
        raise PatchError(f"{NAME}: no glDrawArrays in {tree.rel(path)}")
    tree.set(path, text)
    return path, len(frag), n_draw


def _record_texture_size(tree: SmaliTree) -> tuple[str, str]:
    rpath, _ = render_thread(tree, NAME)
    upload = texture_upload(tree, rpath, NAME)
    calls = list(re.finditer(r"^([ \t]*)invoke-static/range \{v(\d+) \.\. v(\d+)\}, " + re.escape(GL_TEX_IMAGE) + r"\n",
                             upload.body, re.M))
    if len(calls) != 1 or int(calls[0].group(3)) - int(calls[0].group(2)) != 8:
        raise PatchError(f"{NAME}: glTexImage2D call in {upload.name}() has an unexpected shape")
    c = calls[0]
    base = int(c.group(2))
    if base + 4 > 15:
        raise PatchError(f"{NAME}: size registers v{base + 3}/v{base + 4} are beyond v15")
    w, h = f"v{base + 3}", f"v{base + 4}"  # glTexImage2D(target, level, internalformat, width, height, ...)
    hook = (f"{c.group(1)}{MARK}: remember the thermal texture size\n"
            f"{c.group(1)}invoke-static {{{w}, {h}}}, {HELPER}->size(II)V\n\n")
    tree.replace_method_body(rpath, upload, upload.body[:c.start()] + hook + upload.body[c.start():])
    return rpath, upload.name


def _photo(tree: SmaliTree, k: int) -> tuple[str, str, int]:
    found = [(p, m) for p in tree.containing('"_thermal"', DRAW_BITMAP)
             for m in methods(tree.get(p)) if '"_thermal"' in m.body and DRAW_BITMAP in m.body]
    if len(found) != 1:
        raise PatchError(f'{NAME}: expected one photo method ("_thermal" + drawBitmap), found {len(found)}'
                         " -- 1.9.x saves photos differently")
    path, m = found[0]
    call = re.compile(r"^([ \t]*)invoke-virtual (\{" + ", ".join([REG] * 5) + r"\}), " + re.escape(DRAW_BITMAP), re.M)
    n = len(call.findall(m.body))
    if n == 0:
        raise PatchError(f"{NAME}: photo method {m.name}() has no 5-register drawBitmap call")
    body = call.sub(lambda c: f"{c.group(1)}{MARK}: frame bitmap {k}x nearest first\n"
                              f"{c.group(1)}invoke-static {c.group(2)}, {HELPER}->draw(Landroid/graphics/Canvas;"
                              "Landroid/graphics/Bitmap;Landroid/graphics/Rect;Landroid/graphics/Rect;"
                              "Landroid/graphics/Paint;)V", m.body)
    tree.replace_method_body(path, m, body)
    return path, m.name, n


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    shader_path, n_frag, n_draw = _patch_shaders(tree)
    upload_path, upload_name = _record_texture_size(tree)
    photo_path, photo_name, n_photo = _photo(tree, PHOTO_FACTOR)
    tree.add_class(HELPER, HELPER_SMALI.format(mark=MARK, k=PHOTO_FACTOR, sharpness=f"{SHARPNESS!r}f", draw=DRAW_BITMAP))
    report = [f"sharpness {SHARPNESS:g}: {tree.rel(shader_path)}: {n_frag} fragment shader(s) remapped, "
              f"vertex shader highp, thermalSize / thermalSharp before {n_draw} glDrawArrays",
              f"{tree.rel(upload_path)} {upload_name}() records the texture size; "
              f"photo {tree.rel(photo_path)} {photo_name}(): {n_photo} drawBitmap call(s) {PHOTO_FACTOR}x nearest first"]
    return report + optional_settings(tree, NAME, "Upscale", "Upscaling")
