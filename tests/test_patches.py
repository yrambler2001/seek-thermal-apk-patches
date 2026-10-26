"""Every patch against the synthetic smali trees (tests/fixtures): what it changes, and that it
refuses -- without touching anything -- when the code is not there."""
from __future__ import annotations

import re

import pytest
from conftest import SHAPES

from seekpatch import __version__, axml
from seekpatch.patches import (
    BY_NAME,
    Options,
    calibration,
    debug_log,
    default_palette,
    flat_field,
    fps_readout,
    full_fps,
    hidden_settings,
    http_legacy,
    lock_range,
    mic_prompt,
    no_analytics,
    no_smoothing,
    photo_1x,
    png_photos,
    reconnect_fix,
    resume_fix,
    sharp_scaling,
    shutter,
    smart_smoothing,
    smoothing_settings,
    video_quality,
)
from seekpatch.patches.settings import ATTACH, SCREEN
from seekpatch.smali import AlreadyApplied, PatchError, SmaliTree, methods

ABIS = ("arm64-v8a", "armeabi-v7a")


def tree_of(make_project, shape: str, abis: tuple[str, ...] = ABIS) -> SmaliTree:
    return SmaliTree(str(make_project(shape, abis)))


def text(tree: SmaliTree, cls: str) -> str:
    return tree.get(tree.path_of(cls))


# default_palette --------------------------------------------------------------------------------

def test_default_palette(make_project):
    tree = tree_of(make_project, "lambda")
    report = default_palette.apply(tree, Options())
    assert report == ["smali/fix/Prefs.smali b(): color_palette defaults to 4 (Tyrian) instead of 2"]
    prefs = text(tree, "Lfix/Prefs;")
    read = next(m for m in methods(prefs) if m.name == "b")
    assert re.search(r'const-string v0, "color_palette"\n\n\s+\.line 8\n\s+# seek-patch default_palette: Tyrian '
                     r"\(palette 4\) until one is picked, not 2\n\s+const/16 v1, 0x4\n\n\s+\.line 9\n\s+invoke-interface "
                     r"\{p0, v0, v1\}, Landroid/content/SharedPreferences;->getInt", read.body)
    assert "const/4 v1, 0x2" not in read.body
    assert "putInt" in prefs and "seek-patch" not in next(m for m in methods(prefs) if m.name == "Z").body
    with pytest.raises(AlreadyApplied):
        default_palette.apply(tree, Options())


def test_default_palette_reads_a_filled_array(make_project):
    root = make_project("lambda")
    names = ["White", "Black", "Spectra", "Tyrian", "Iron"]  # Tyrian third here: the index comes from the list
    consts = "\n\n".join(f'    const-string v{i + 1}, "{n}"' for i, n in enumerate(names))
    (root / "smali" / "fix" / "Palettes.smali").write_text(
        ".class public Lfix/Palettes;\n.super Ljava/lang/Object;\n\n.method static f()V\n    .locals 6\n\n"
        f"{consts}\n\n    filled-new-array/range {{v1 .. v5}}, [Ljava/lang/String;\n\n    move-result-object v0\n\n"
        "    return-void\n.end method\n")
    tree = SmaliTree(str(root))
    assert default_palette.apply(tree, Options())[0].endswith("defaults to 3 (Tyrian) instead of 2")
    assert "const/16 v1, 0x3" in text(tree, "Lfix/Prefs;")


def test_default_palette_needs_the_palette_list(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Palettes.smali").unlink()
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match='palette list with "Tyrian"'):
        default_palette.apply(tree, Options())
    assert "seek-patch" not in text(tree, "Lfix/Prefs;")


# full_fps ---------------------------------------------------------------------------------------

DRAW_CALL = {  # what the thermal handler gains, per shape
    "lambda": ("Lfix/Render;", "invoke-direct {p0}, Lfix/Render;->D()V"),
    "accessor": ("Lfix/Render$e;", "invoke-static {v1}, Lfix/Render;->b(Lfix/Render;)V"),
    "virtual": ("Lfix/Render$f;", "invoke-virtual {v0}, Lfix/Render;->h()V"),
}
CAMERA = {"lambda": "Lfix/Render;", "accessor": "Lfix/Render$c;", "virtual": "Lfix/Render$d;"}


@pytest.mark.parametrize("shape", SHAPES)
def test_full_fps_moves_the_draw(make_project, shape):
    tree = tree_of(make_project, shape)
    report = full_fps.apply(tree, Options())
    assert report and "Lfix/Render;" in report[0]
    site_cls, call = DRAW_CALL[shape]
    site = text(tree, site_cls)
    assert re.search(r"->(i|h|a|d)\([^)]*\)V\n\n\s+# seek-patch full_fps: present every thermal frame\n\s+"
                     + re.escape(call), site)
    camera = next(m for m in methods(text(tree, CAMERA[shape])) if "updateTexImage" in m.body)
    assert "# seek-patch full_fps: no redraw per camera frame" in camera.body
    assert not re.search(r"invoke-\w+ \{\w+\}, Lfix/Render;->(D|w|h|b)\(", camera.body)


def test_full_fps_refuses_without_a_render_thread(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Render.smali").unlink()
    with pytest.raises(PatchError, match="ThermalPlusRenderThread"):
        full_fps.apply(SmaliTree(str(root)), Options())


# sharp_scaling ----------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_sharp_scaling(make_project, shape):
    tree = tree_of(make_project, shape)
    sharp_scaling.apply(tree, Options(sharpness=2.0))
    program = text(tree, "Lfix/Program;")
    assert program.count("texture2D(thermalTexture, sharpCoord(vTextureCoord))") == 2
    assert program.count("varying SHARP_P vec2 vTextureCoord;") == 2
    assert "(t - i - 0.5) * thermalSharp + 0.5" in program
    assert "if (thermalSize.x < 1.0 || thermalSharp <= 1.0) return c;" in program  # Android: the stock sample
    assert "#ifdef GL_FRAGMENT_PRECISION_HIGH" in program and "#define SHARP_OFF" in program
    assert "precision highp float;\\nuniform mat4 uTexMatrix;" in program  # the vertex shader
    assert re.search(r"invoke-static \{\}, Lseekpatch/SharpScale;->uniform\(\)V\n\n\s+invoke-static \{v0, v1, v2\}, "
                     r"Landroid/opengl/GLES20;->glDrawArrays", program)
    render = text(tree, "Lfix/Render;")
    assert re.search(r"invoke-static \{v5, v6\}, Lseekpatch/SharpScale;->size\(II\)V\n\n\s+invoke-static/range "
                     r"\{v2 \.\. v10\}, Landroid/opengl/GLES20;->glTexImage2D", render)
    photo = text(tree, "Lfix/Pipeline;")
    assert photo.count("Lseekpatch/SharpScale;->draw(") == 2
    assert "Canvas;->drawBitmap(" not in photo
    helper = text(tree, "Lseekpatch/SharpScale;")
    assert ".field public static sharpness:F = 2.0f" in helper and ".field public static photoFactor:I = 2" in helper
    assert "glUniform2f" in helper and 'const-string v0, "thermalSharp"' in helper and "glUniform1f" in helper
    # photoFactor 0 (Blocky): the frame drawn with an unfiltered copy of the paint
    assert re.search(r"sget v5, Lseekpatch/SharpScale;->photoFactor:I\n\s+if-nez v5, :factor\n\s+if-eqz p4, :draw\n"
                     r"\s+new-instance v0, Landroid/graphics/Paint;\n\s+invoke-direct \{v0, p4\}, Landroid/graphics/Paint;"
                     r"-><init>\(Landroid/graphics/Paint;\)V\n\s+const/4 v1, 0x0\n\s+invoke-virtual \{v0, v1\}, "
                     r"Landroid/graphics/Paint;->setFilterBitmap\(Z\)V\n\s+move-object p4, v0\n\s+goto :draw\n", helper)
    # the settings: Upscale, behind the shared hooks
    assert tree.path_of("Lseekpatch/Upscale;") and tree.path_of("Lseekpatch/Settings;")
    assert text(tree, "Lfix/ImageSettings;").count(SCREEN) == 1


def test_sharp_scaling_sharpness_is_configurable(make_project):
    tree = tree_of(make_project, "lambda")
    report = sharp_scaling.apply(tree, Options(sharpness=3.5))
    helper = text(tree, "Lseekpatch/SharpScale;")  # where the settings start
    assert ".field public static sharpness:F = 3.5f" in helper
    assert ".field public static photoFactor:I = 4" in helper  # photo path rounds to an integer factor
    assert report[0].startswith("sharpness 3.5")
    assert report[-1] == "settings: Upscaling (seekpatch.Upscale)"


def test_sharp_scaling_without_a_settings_screen(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "ImageSettings.smali").unlink()
    tree = SmaliTree(str(root))
    report = sharp_scaling.apply(tree, Options())
    assert report[-1].startswith("no settings: expected one PreferenceFragment")
    assert not tree.path_of("Lseekpatch/Upscale;") and not tree.path_of("Lseekpatch/Settings;")
    assert "thermalSharp" in text(tree, "Lseekpatch/SharpScale;")  # the field keeps --sharpness


@pytest.mark.parametrize("bad", [1.0, 0.5, 100.0])
def test_sharp_scaling_rejects_bad_sharpness(make_project, bad):
    with pytest.raises(PatchError, match="sharpness"):
        sharp_scaling.apply(tree_of(make_project, "lambda"), Options(sharpness=bad))


# no_smoothing -----------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_no_smoothing(make_project, shape):
    tree = tree_of(make_project, shape)
    report = no_smoothing.apply(tree, Options())
    assert "Lfix/NativeLib;->g(JILjava/nio/ByteBuffer;I)I" in report[0]
    pipeline = text(tree, "Lfix/Pipeline;")
    assert re.search(r"Lfix/Pipeline;->set\(JLfix/Features;I\)V\n\n\s+# seek-patch no_smoothing\n\s+invoke-static/range "
                     r"\{p0 \.\. p2\}, Lfix/Pipeline;->seekpatch_nosmoothing_apply\(Lfix/Pipeline;J\)V", pipeline)
    assert "iget-boolean v0, p0, Lfix/Pipeline;->C:Z" in pipeline
    assert "const/16 v0, 0x66" in pipeline and "const/16 v0, 0x64" in pipeline  # features 102 and 100
    assert "invoke-static {p0, p1, p2, v0, v1}, Lfix/NativeLib;->g(JILjava/nio/ByteBuffer;I)I" in pipeline


def test_no_smoothing_refuses_older_apps(make_project):
    tree = tree_of(make_project, "lambda")
    tree._identity = {"versionCode": 240, "versionName": "2.1.6"}
    with pytest.raises(PatchError, match="2.1.6"):
        no_smoothing.apply(tree, Options())


def test_no_smoothing_needs_the_feature_call(make_project):
    with pytest.raises(PatchError, match="feature-900 call"):
        no_smoothing.apply(tree_of(make_project, "virtual"), Options())


# debug_log --------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_debug_log(make_project, shape):
    tree = tree_of(make_project, shape)
    debug_log.apply(tree, Options())
    log = text(tree, "Lfix/Log;")
    assert log.count("Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I") == 2
    assert 'const-string v0, "Seekware"' in log


def test_debug_log_refuses_a_real_method(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Log.smali"
    p.write_text(p.read_text().replace("    .line 1\n    return-void", "    nop\n    return-void", 1))
    with pytest.raises(PatchError, match="not an empty stub"):
        debug_log.apply(SmaliTree(str(root)), Options())


# png_photos -------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_png_photos(make_project, shape):
    tree = tree_of(make_project, shape)
    png_photos.apply(tree, Options())
    reader = next(m for m in methods(text(tree, "Lfix/Prefs;")) if m.name == "H")
    assert re.search(r"sget v0, Landroid/os/Build\$VERSION;->SDK_INT:I\n\s+const/16 v1, 0x1e\n\s+if-lt v0, v1, "
                     r":seekpatch_stock\n\s+const/4 v0, 0x1\n\s+return v0\n\s+:seekpatch_stock", reader.body)
    setter = next(m for m in methods(text(tree, "Lfix/Pipeline;")) if m.name == "O0")
    assert ".locals 2" in setter.body and "const/4 p1, 0x1" in setter.body
    # Android 10 and older keep the app's value: p1 is not touched on that path
    assert setter.body.index(":seekpatch_stock") < setter.body.index("iput-boolean p1, p0, Lfix/Pipeline;->M:Z")
    assert "const/16 p1" not in setter.body


def test_png_photos_needs_the_preference(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Prefs.smali").unlink()
    with pytest.raises(PatchError, match="lossless_comp_key"):
        png_photos.apply(SmaliTree(str(root)), Options())


# photo_1x ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_photo_1x(make_project, shape):
    tree = tree_of(make_project, shape)
    report = photo_1x.apply(tree, Options())
    pipeline = text(tree, "Lfix/Pipeline;")
    e0 = next(m for m in methods(pipeline) if m.name == "e0")
    assert re.search(r"\.locals 5\n\n\s+# seek-patch photo_1x[^\n]*\n\s+iget-object v0, p0, Lfix/Pipeline;->ctx:"
                     r"Landroid/content/Context;\n\s+invoke-static \{v0, p2\}, Lseekpatch/Photo1x;->capture\("
                     r"Landroid/content/Context;Landroid/graphics/Bitmap;\)V\n\n\s+new-instance v0", e0.body)
    exif = next(m for m in methods(pipeline) if m.name == "T")
    assert re.search(r"invoke-static \{\}, Lfix/Pipeline;->o0\(\)I\n\s+move-result v0\n\s+invoke-static \{p2, v0\}, "
                     r"Lseekpatch/Photo1x;->saved\(Ljava/io/File;I\)V\n\n\s+return-void", exif.body)
    assert tree.path_of("Lseekpatch/Photo1x;")
    assert report[-1] == "settings: Also save a 1x PNG (seekpatch.PhotoSettings)"
    assert tree.path_of("Lseekpatch/PhotoSettings;") and tree.path_of("Lseekpatch/Settings;")
    # on unless the setting says otherwise: without a settings screen the patch saves with every photo
    assert ".field public static volatile enabled:Z = true" in text(tree, "Lseekpatch/Photo1x;")


def test_photo_1x_without_a_settings_screen(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "ImageSettings.smali").unlink()
    tree = SmaliTree(str(root))
    report = photo_1x.apply(tree, Options())
    assert report[-1].startswith("no settings: expected one PreferenceFragment")
    assert tree.path_of("Lseekpatch/Photo1x;") and not tree.path_of("Lseekpatch/PhotoSettings;")


def test_photo_1x_needs_the_exif_writer(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Pipeline.smali"
    p.write_text(p.read_text().replace("saveAttributes", "getThumbnail"))
    with pytest.raises(PatchError, match="EXIF method"):
        photo_1x.apply(SmaliTree(str(root)), Options())


# video_quality ----------------------------------------------------------------------------------

UPLOAD_SITE = {"lambda": ("Lfix/Render;", "p0"), "accessor": ("Lfix/Render$e;", "v1")}


@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_video_quality(make_project, shape):
    tree = tree_of(make_project, shape)
    report = video_quality.apply(tree, Options())
    assert report[0].startswith("HEVC QP 18")
    assert report[-1] == "settings: Video quality (seekpatch.VideoSettings)"
    assert tree.path_of("Lseekpatch/VideoSettings;") and ".field public static qp:I = 0x12" in text(tree, "Lseekpatch/VideoConfig;")
    recorder = text(tree, "Lfix/Recorder;")
    assert re.search(r"invoke-static \{p1\}, Lseekpatch/Video;->encoder\(Landroid/media/MediaFormat;\)"
                     r"Landroid/media/MediaCodec;\n\n\s+move-result-object p2", recorder)
    assert "MediaCodec;->configure(" not in recorder and "createEncoderByType" not in recorder
    sound = text(tree, "Lfix/Sound;")
    assert "invoke-static {v0, v1, v2}, Lseekpatch/Audio;->minBufferSize(III)I" in sound
    assert re.search(r"Audio;->rate\(\)I\n\s+move-result v4\n\s+invoke-static \{\}, Lseekpatch/Audio;->channelMask\(\)I\n"
                     r"\s+move-result v5\n\s+invoke-direct/range \{v2 \.\. v7\}, Landroid/media/AudioRecord;-><init>", sound)
    assert "invoke-static {v1, v0, v3, v3, v2}, Lseekpatch/Audio;->configure(" in sound
    render = text(tree, "Lfix/Render;")
    frame = next(m for m in methods(render) if m.name == "seekpatchVideoFrame")
    assert "public" in frame.header.split() and "glFinish" in frame.body
    assert "iget-object v0, p0, Lfix/Render;->b:Lfix/Encoder;" in frame.body
    assert "invoke-virtual {v0, v1}, Lfix/Encoder;->e(Landroid/graphics/SurfaceTexture;)V" in frame.body
    site_cls, inst = UPLOAD_SITE[shape]
    assert f"invoke-virtual {{{inst}}}, Lfix/Render;->seekpatchVideoFrame()V" in text(tree, site_cls)
    camera = next(m for m in methods(text(tree, CAMERA[shape])) if "updateTexImage" in m.body)
    assert "Lfix/Encoder;->e(" not in camera.body and "nop" in camera.body
    config = text(tree, "Lseekpatch/VideoConfig;")
    assert 'mime:Ljava/lang/String; = "video/hevc"' in config and "qp:I = 0x12" in config
    assert "longSide:I = 0x500" in config
    assert tree.path_of("Lseekpatch/Video;") and tree.path_of("Lseekpatch/Video$Candidate;") and tree.path_of("Lseekpatch/Audio;")


def test_settings_hooks_are_shared(make_project):
    tree = tree_of(make_project, "lambda")
    for p in (sharp_scaling, smoothing_settings, video_quality, flat_field, photo_1x):
        report = p.apply(tree, Options())
        assert not any(line.startswith("no settings") for line in report)
    assert text(tree, "Lfix/ImageSettings;").count(SCREEN) == 1 and text(tree, "Lfix/Main;").count(ATTACH) == 1
    assert "# seek-patch sharp_scaling: seek-patch's settings" in text(tree, "Lfix/ImageSettings;")  # the first
    sections = ("Filters", "FlatSettings", "Upscale", "PhotoSettings", "VideoSettings")
    assert all(tree.path_of(f"Lseekpatch/{c};") for c in sections + ("Settings", "Screens", "Screens$1"))
    # the side menu's credit shows the version of seek-patch that patched the app
    assert f'.field public static version:Ljava/lang/String; = "{__version__}"' in text(tree, "Lseekpatch/About;")
    assert "Lseekpatch/About;->version:Ljava/lang/String;" in text(tree, "Lseekpatch/Screens;")
    # Settings looks the sections up by name: the names it lists are the classes the patches add
    settings = text(tree, "Lseekpatch/Settings;")
    assert all(f'"seekpatch.{c}"' in settings for c in sections)


def test_video_quality_options(make_project):
    tree = tree_of(make_project, "lambda")
    video_quality.apply(tree, Options(video_codec="avc", video_qp=24))
    config = text(tree, "Lseekpatch/VideoConfig;")
    assert '"video/avc"' in config and "qp:I = 0x18" in config


@pytest.mark.parametrize("bad", [{"video_codec": "vp9"}, {"video_qp": 5}, {"video_qp": 60}])
def test_video_quality_rejects_bad_options(make_project, bad):
    with pytest.raises(PatchError, match="video"):
        video_quality.apply(tree_of(make_project, "lambda"), Options(**bad))


def test_video_quality_needs_the_encoder_handoff(make_project):
    with pytest.raises(PatchError, match="feeds the video encoder"):
        video_quality.apply(tree_of(make_project, "virtual"), Options())


def test_video_quality_refuses_a_reused_format_register(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Recorder.smali"
    p.write_text(p.read_text().replace('const-string p2, "bitrate"', 'const-string p1, "bitrate"'))
    with pytest.raises(PatchError, match="format register"):
        video_quality.apply(SmaliTree(str(root)), Options())


# resume_fix -------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_resume_fix(make_project, shape):
    tree = tree_of(make_project, shape)
    resume_fix.apply(tree, Options())
    pause = next(m for m in methods(text(tree, "Lfix/Render;")) if m.name == "v")
    assert re.search(r"invoke-static \{\}, Lseekpatch/Egl;->releaseWindow\(\)V\n\n\s+const/4 v0, 0x0\n\s+"
                     r"iput-object v0, p0, Lfix/Render;->g:Lfix/Window;", pause.body)
    assert tree.path_of("Lseekpatch/Egl;")


def test_resume_fix_needs_the_window(make_project):
    with pytest.raises(PatchError, match="window-surface field"):
        resume_fix.apply(tree_of(make_project, "virtual"), Options())


# reconnect_fix ----------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_reconnect_fix(make_project, shape):
    tree = tree_of(make_project, shape)
    assert reconnect_fix.apply(tree, Options()) == [
        "smali/fix/Camera.smali L(Landroid/content/Context;)V: the USB receiver stays registered",
        "smali/fix/Camera.smali: cameras left open by the last camera screen (list b) are closed "
        "(Lfix/CameraDevice;->C0), released (Lfix/UsbLink;->a) and opened again when the next one registers",
        "smali/fix/Camera.smali: the permission answer is addressed to this app, and on Android 13+ the receiver hears "
        "no other app (PendingIntents: 1, registrations: 2)"]
    cls = text(tree, "Lfix/Camera;")
    init = next(m for m in methods(cls) if m.name == "<init>")  # the answer is addressed to this app
    assert re.search(r"invoke-static \{v0, p1\}, Lfix/Camera;->seekpatch_own\(Landroid/content/Intent;Landroid/content/"
                     r"Context;\)V\n\n\s+invoke-static \{p1, v2, v0, v2\}, Landroid/app/PendingIntent;->getBroadcast",
                     init.body)
    register = ("invoke-static {p1, p0, v0}, Lfix/Camera;->seekpatch_register(Landroid/content/Context;"
                "Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;")
    assert init.body.count(register) == 2  # with and without flags, both through the helper
    assert "Lfix/Compat;->a(" not in init.body and "Landroid/content/Context;->registerReceiver(" not in init.body
    helper = next(m for m in methods(cls) if m.name == "seekpatch_register")
    assert re.search(r"const/4 v0, 0x4\n\n\s+invoke-virtual \{p0, p1, p2, v0\}, Landroid/content/Context;->registerReceiver"
                     r"\(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I\)", helper.body)  # not exported
    own = next(m for m in methods(cls) if m.name == "seekpatch_own")
    assert "Landroid/content/Intent;->setPackage(Ljava/lang/String;)Landroid/content/Intent;" in own.body
    unregister = next(m for m in methods(cls) if m.name == "L")
    assert "unregisterReceiver" not in unregister.body
    assert re.search(r"# seek-patch reconnect_fix: [^\n]*\n\s+return-void\n$", unregister.body)
    listener = next(m for m in methods(cls) if m.name == "D")  # the release runs before the search's check
    assert re.search(r"iput-object p1, p0, Lfix/Camera;->d:Ljava/lang/Runnable;\n\n\s+# seek-patch reconnect_fix: "
                     r"[^\n]*\n\s+invoke-direct \{p0\}, Lfix/Camera;->seekpatch_release\(\)V\n\n\s+"
                     r"iget-object p1, p0, Lfix/Camera;->b:Ljava/util/ArrayList;", listener.body)
    release = next(m for m in methods(cls) if m.name == "seekpatch_release")
    assert release.is_private
    assert re.search(r"invoke-virtual \{v0, v1\}, Ljava/util/ArrayList;->remove\(I\)Ljava/lang/Object;\n\n\s+"
                     r"move-result-object v1\n\n\s+check-cast v1, Lfix/CameraDevice;\n\n\s+:seekpatch_try_start\n\s+"
                     r"invoke-virtual \{v1\}, Lfix/CameraDevice;->C0\(\)V\n\n\s+"
                     r"iget-object v2, p0, Lfix/Camera;->n:Lfix/UsbLink;\n\n\s+"
                     r"invoke-virtual \{v1\}, Lfix/CameraDevice;->Z\(\)Lfix/UsbHolder;\n\n\s+move-result-object v1\n\n\s+"
                     r"invoke-virtual \{v2, v1\}, Lfix/UsbLink;->a\(Lfix/UsbHolder;\)I\n", release.body)
    unplug = next(m for m in methods(cls) if m.name == "t")
    assert "seek-patch" not in unplug.body  # unplugging is Seek's own
    with pytest.raises(AlreadyApplied):
        reconnect_fix.apply(tree, Options())


def test_reconnect_fix_on_an_older_library(make_project):
    root = make_project("lambda")  # 2.2.x: the DeviceManager keeps the camera, so only the receiver is kept
    path = root / "smali" / "fix" / "Camera.smali"
    path.write_text(path.read_text().replace("    invoke-virtual {v0}, Lfix/CameraDevice;->C0()V\n", ""))
    tree = SmaliTree(str(root))
    assert reconnect_fix.apply(tree, Options())[1] == (
        "smali/fix/Camera.smali: no camera to release: up to 2.2.3 the DeviceManager lives as long as the process "
        "and keeps its camera for the next screen")
    cls = text(tree, "Lfix/Camera;")
    assert "unregisterReceiver" not in next(m for m in methods(cls) if m.name == "L").body
    assert "seekpatch_release" not in cls


def test_reconnect_fix_leaves_a_library_registered_again(make_project):
    root = make_project("lambda")  # up to 2.1.7 the camera screen registers the library again when it starts
    path = root / "smali" / "fix" / "Camera.smali"
    path.write_text(path.read_text() + """
.method public static k(Landroid/content/Context;)V
    .locals 2

    sget-object v0, Lfix/Camera;->t:Lfix/Camera;

    new-instance v1, Landroid/content/IntentFilter;

    invoke-direct {v1}, Landroid/content/IntentFilter;-><init>()V

    invoke-virtual {p0, v0, v1}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;

    return-void
.end method
""")
    (root / "smali" / "fix" / "Screen.smali").write_text(
        ".class Lfix/Screen;\n.super Ljava/lang/Object;\n\n.method static a(Landroid/content/Context;)V\n    .locals 0\n\n"
        "    invoke-static {p0}, Lfix/Camera;->k(Landroid/content/Context;)V\n\n    return-void\n.end method\n")
    tree = SmaliTree(str(root))
    report = reconnect_fix.apply(tree, Options())
    assert report[0] == ("smali/fix/Camera.smali L(Landroid/content/Context;)V: left as is -- the app registers the "
                         "receiver again (k(Landroid/content/Context;)V) whenever a camera screen starts")
    assert report[2].endswith("(PendingIntents: 1, registrations: 3)")  # the registration again is not exported either
    cls = text(tree, "Lfix/Camera;")
    assert "unregisterReceiver" in next(m for m in methods(cls) if m.name == "L").body
    assert "seekpatch_register" in next(m for m in methods(cls) if m.name == "k").body


def test_reconnect_fix_needs_the_library(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Camera.smali").unlink()
    with pytest.raises(PatchError, match="one Seekware library receiver"):
        reconnect_fix.apply(SmaliTree(str(root)), Options())


def test_reconnect_fix_unregisters_only_the_library(make_project):
    root = make_project("lambda")
    path = root / "smali" / "fix" / "Camera.smali"
    path.write_text(path.read_text().replace("    .line 1\n    sget-object v0, Lfix/Camera;->t:Lfix/Camera;",
                                             "    .line 1\n    sget-object v0, Lfix/Camera;->p:Landroid/app/PendingIntent;"))
    with pytest.raises(PatchError, match="does not unregister the library"):
        reconnect_fix.apply(SmaliTree(str(root)), Options())


def test_reconnect_fix_needs_a_close_that_releases_the_connection(make_project):
    root = make_project("lambda")
    path = root / "smali" / "fix" / "UsbLink.smali"
    path.write_text(path.read_text().replace(
        "    invoke-virtual {v0}, Landroid/hardware/usb/UsbDeviceConnection;->close()V\n", ""))
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match="releases the interface and closes the connection"):
        with tree.transaction():
            reconnect_fix.apply(tree, Options())
    assert tree.save() == []  # the receiver kept before it was rolled back


def test_reconnect_fix_needs_the_permission_request(make_project):
    root = make_project("lambda")
    path = root / "smali" / "fix" / "Camera.smali"
    path.write_text(re.sub(r"    invoke-static \{p1, v2, v0, v2\}, Landroid/app/PendingIntent;->getBroadcast[^\n]*\n\n"
                           r"    move-result-object v0\n\n    sput-object v0, Lfix/Camera;->p:Landroid/app/PendingIntent;\n",
                           "", path.read_text()))
    with pytest.raises(PatchError, match="permission request's PendingIntent"):
        reconnect_fix.apply(SmaliTree(str(root)), Options())


def test_reconnect_fix_needs_the_listener_registration(make_project):
    root = make_project("lambda")
    path = root / "smali" / "fix" / "Camera.smali"
    path.write_text(path.read_text().replace("    invoke-direct {p0}, Lfix/Camera;->G()V\n", ""))
    with pytest.raises(PatchError, match="one listener registration"):
        reconnect_fix.apply(SmaliTree(str(root)), Options())


# no_analytics -----------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_no_analytics(make_project, shape):
    tree = tree_of(make_project, shape)
    assert no_analytics.apply(tree, Options()) == [
        "smali/fix/Analytics.smali run(): disabled before it starts (e), queue drained -- no Lfix/Uploader;: "
        "no Google Play services connection, no hit store, nothing sent"]
    cls = text(tree, "Lfix/Analytics;")
    run = next(m for m in methods(cls) if m.name == "run")
    assert "Lfix/Uploader;" not in run.body  # never set up
    assert "invoke-interface" not in run.body  # the queued work is dropped, not run
    assert re.search(r"const/4 v0, 0x1\n\n\s+iput-boolean v0, p0, Lfix/Analytics;->e:Z\n", run.body)  # the disabled flag
    assert re.search(r":seekpatch_next\n\s+iget-boolean v0, p0, Lfix/Analytics;->c:Z\n\n\s+if-nez v0, :seekpatch_closed", run.body)
    assert re.search(r"iget-object v0, p0, Lfix/Analytics;->g:Ljava/util/concurrent/LinkedBlockingQueue;\n\n\s+"
                     r"invoke-virtual \{v0\}, Ljava/util/concurrent/LinkedBlockingQueue;->take\(\)Ljava/lang/Object;\n"
                     r"\s+:seekpatch_try_end\n\s+\.catch Ljava/lang/InterruptedException;", run.body)
    assert all("seek-patch" not in m.body for m in methods(cls) if m.name != "run")  # the app still queues its work
    with pytest.raises(AlreadyApplied):
        no_analytics.apply(tree, Options())


def test_no_analytics_needs_the_thread(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Analytics.smali").unlink()
    with pytest.raises(PatchError, match="one Google Analytics thread"):
        no_analytics.apply(SmaliTree(str(root)), Options())


def test_no_analytics_needs_the_work_loop(make_project):
    root = make_project("lambda")
    path = root / "smali" / "fix" / "Analytics.smali"
    path.write_text(path.read_text().replace("    check-cast v1, Ljava/lang/Runnable;\n", ""))
    with pytest.raises(PatchError, match="one work loop"):
        no_analytics.apply(SmaliTree(str(root)), Options())


def test_no_analytics_refuses_a_proxy_made_elsewhere(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Other.smali").write_text(
        ".class Lfix/Other;\n.super Ljava/lang/Object;\n\n.method static a(Landroid/content/Context;)V\n    .locals 2\n\n"
        "    new-instance v0, Lfix/Uploader;\n\n    const/4 v1, 0x0\n\n"
        "    invoke-direct {v0, p0, v1}, Lfix/Uploader;-><init>(Landroid/content/Context;Ljava/lang/Thread;)V\n\n"
        "    return-void\n.end method\n")
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match="created in 2 places"):
        no_analytics.apply(tree, Options())
    assert tree.save() == []


# http_legacy ------------------------------------------------------------------------------------

LIBRARY = "org.apache.http.legacy"


def _binary_manifest(root, edit) -> None:
    """Rewrite the project's binary manifest through axml.Document."""
    path = root / "AndroidManifest.xml"
    doc = axml.Document(path.read_bytes())
    edit(doc)
    path.write_bytes(doc.to_bytes())


@pytest.mark.parametrize("shape", SHAPES)
def test_http_legacy(make_project, shape):
    root = make_project(shape)
    tree = SmaliTree(str(root))
    assert http_legacy.apply(tree, Options()) == [
        'AndroidManifest.xml: <uses-library android:name="org.apache.http.legacy" android:required="false"/> '
        "(targetSdkVersion 35; Apache HTTP used in 1 classes)"]
    assert axml.uses_libraries(tree.manifest) == [(LIBRARY, "seek-patch http_legacy")]
    with pytest.raises(AlreadyApplied):
        http_legacy.apply(tree, Options())
    assert tree.save() == ["AndroidManifest.xml"]
    assert axml.uses_libraries((root / "AndroidManifest.xml").read_bytes()) == [(LIBRARY, "seek-patch http_legacy")]
    with pytest.raises(AlreadyApplied):  # from the file, as when an already patched apk comes back
        http_legacy.apply(SmaliTree(str(root)), Options())


def test_http_legacy_in_a_text_manifest(make_project):  # --side-by-side decodes the manifest
    root = make_project("lambda")
    (root / "AndroidManifest.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        'package="org.example.seekfixture">\n    <application android:label="Fixture">\n'
        '        <activity android:name=".MainActivity"/>\n    </application>\n</manifest>\n')
    (root / "apktool.yml").write_text((root / "apktool.yml").read_text().replace(
        "  minSdkVersion: 19\n", "  minSdkVersion: 19\n  targetSdkVersion: 30\n"))
    tree = SmaliTree(str(root))
    assert "targetSdkVersion 30" in http_legacy.apply(tree, Options())[0]
    assert ('    <application android:label="Fixture">\n        <!-- seek-patch http_legacy -->\n'
            '        <uses-library android:name="org.apache.http.legacy" android:required="false"/>\n') in tree.manifest.decode()
    with pytest.raises(AlreadyApplied):
        http_legacy.apply(tree, Options())


def test_http_legacy_leaves_an_app_that_declares_it(make_project):  # 2.3.3, 2.3.4
    root = make_project("lambda")
    (root / "AndroidManifest.xml").write_bytes(
        axml.add_uses_library((root / "AndroidManifest.xml").read_bytes(), LIBRARY, False))
    with pytest.raises(PatchError, match="already declares") as e:
        http_legacy.apply(SmaliTree(str(root)), Options())
    assert not isinstance(e.value, AlreadyApplied)  # the default set skips it


def test_http_legacy_leaves_an_app_that_targets_27(make_project):  # up to 2.1.5: Android adds the library
    root = make_project("lambda")

    def target_27(doc):
        doc.attribute(doc.nodes[doc.elements("uses-sdk")[0]], axml.TARGET_SDK_VERSION).data = 27
    _binary_manifest(root, target_27)
    with pytest.raises(PatchError, match="targets API 27"):
        http_legacy.apply(SmaliTree(str(root)), Options())


def test_http_legacy_needs_a_use_of_apache_http(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Uploader.smali").unlink()
    with pytest.raises(PatchError, match="does not use Apache HTTP"):
        http_legacy.apply(SmaliTree(str(root)), Options())


def test_a_failing_patch_leaves_the_manifest_untouched(make_project):
    root = make_project("lambda")
    before = (root / "AndroidManifest.xml").read_bytes()
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match="later"):
        with tree.transaction():
            http_legacy.apply(tree, Options())
            raise PatchError("a later step fails")
    assert tree.manifest == before
    assert tree.save() == []


# mic_prompt -------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_mic_prompt(make_project, shape):
    tree = tree_of(make_project, shape)
    mic_prompt.apply(tree, Options())
    main = text(tree, "Lfix/Main;")
    y = next(m for m in methods(main) if m.name == "Y0")
    assert re.search(r"iget-boolean v6, p0, Lfix/Main;->s9:Z\n\s+invoke-static \{p0, p2, v6\}, Lseekpatch/Mic;->gate\("
                     r"Landroid/app/Activity;IZ\)I\n\n\s+move-result v6", y.body)
    assert "invoke-static {p0, v5, v3}, Lseekpatch/Mic;->request(Landroid/app/Activity;[Ljava/lang/String;I)V" in y.body
    assert y.body.count("Lfix/Outline;->a(") == 1  # the second, real check (the audio flag) stays
    on_result = next(m for m in methods(main) if m.name == "onRequestPermissionsResult")
    assert "invoke-super {p0, p1, p2, p3}, Landroid/app/Activity;->onRequestPermissionsResult" in on_result.body
    assert re.search(r"const/4 v1, 0x3\n\s+invoke-direct \{p0, v1\}, Lfix/Main;->S0\(I\)V", on_result.body)
    assert "invoke-virtual {p0, v0, v1}, Lfix/Main;->Y0(Ljava/lang/String;I)V" in on_result.body
    site_cls = {"lambda": "Lfix/Render;", "accessor": "Lfix/Render$e;", "virtual": "Lfix/Render$f;"}[shape]
    assert "invoke-static {}, Lseekpatch/Mic;->frame()V" in text(tree, site_cls)
    assert all(tree.path_of(f"Lseekpatch/Mic{s};") for s in ("", "$1", "$2", "$3"))


def test_mic_prompt_needs_the_check(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Outline.smali"
    p.write_text(p.read_text().replace("requestPermissions", "shouldShowRequestPermissionRationale"))
    with pytest.raises(PatchError, match="check-request-return"):
        mic_prompt.apply(SmaliTree(str(root)), Options())


# flat_field -------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_flat_field(make_project, shape):
    tree = tree_of(make_project, shape)
    report = flat_field.apply(tree, Options())
    assert re.search(r"Lfix/Pipeline;->set\(JLfix/Features;I\)V\n\n\s+# seek-patch flat_field: .*\n\s+"
                     r"invoke-static \{p1, p2\}, Lseekpatch/Flat;->frame\(J\)V\n", text(tree, "Lfix/Pipeline;"))
    # the settings load first (their hook is added second, at the same place), then the button
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch flat_field: .*\n\s+invoke-static/range \{p0 \.\. p0\}, "
                     + re.escape(ATTACH) + r"\n\n\s+# seek-patch flat_field: .*\n\s+"
                     r"invoke-static \{p0\}, Lseekpatch/Flat;->attach\(Landroid/app/Activity;\)V\n", text(tree, "Lfix/Main;"))
    seekip = text(tree, "Lseekpatch/SeekIP;")
    assert "invoke-static/range {p0 .. p4}, Lfix/NativeLib;->c(JILjava/nio/ByteBuffer;I)I" in seekip
    assert "invoke-static/range {p0 .. p4}, Lfix/NativeLib;->g(JILjava/nio/ByteBuffer;I)I" in seekip
    assert all(tree.path_of(f"Lseekpatch/Flat{s};") for s in ("", "$1", "$2", "$3", "$4", "$5"))
    assert "Lfix/NativeLib;->c(" in report[0]
    assert report[-1] == "settings: Flat field frames (seekpatch.FlatSettings)"
    assert tree.path_of("Lseekpatch/FlatSettings;") and tree.path_of("Lseekpatch/Settings;")


def test_flat_field_shares_the_feature_call_with_no_smoothing(make_project):
    tree = tree_of(make_project, "lambda")
    no_smoothing.apply(tree, Options())
    flat_field.apply(tree, Options())
    pipeline = text(tree, "Lfix/Pipeline;")
    assert "invoke-static {p1, p2}, Lseekpatch/Flat;->frame(J)V" in pipeline
    assert "invoke-static/range {p0 .. p2}, Lfix/Pipeline;->seekpatch_nosmoothing_apply(Lfix/Pipeline;J)V" in pipeline


def test_flat_field_refuses_older_apps(make_project):
    tree = tree_of(make_project, "lambda")
    tree._identity = {"versionCode": 240, "versionName": "2.1.6"}
    with pytest.raises(PatchError, match="2.1.6"):
        flat_field.apply(tree, Options())


def test_flat_field_needs_the_camera_activity(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Main.smali"
    p.write_text(p.read_text().replace("Landroid/view/SurfaceView;", "Landroid/view/TextureView;"))
    with pytest.raises(PatchError, match="SurfaceView"):
        flat_field.apply(SmaliTree(str(root)), Options())


def test_flat_field_needs_a_callable_getfeature(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "NativeLib.smali"
    p.write_text(p.read_text().replace(".method public static c(", ".method static c("))
    with pytest.raises(PatchError, match="callable seekIPgetFeature"):
        flat_field.apply(SmaliTree(str(root)), Options())


# lock_range -------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_lock_range(make_project, shape):
    tree = tree_of(make_project, shape)
    report = lock_range.apply(tree, Options())
    assert re.search(r"Lfix/Pipeline;->set\(JLfix/Features;I\)V\n\n\s+# seek-patch lock_range: .*\n\s+"
                     r"invoke-static \{\}, Lseekpatch/Lock;->frame\(\)V\n", text(tree, "Lfix/Pipeline;"))
    stream = text(tree, "Lfix/Stream;")
    assert re.search(r"\.line 1\n\s+# seek-patch lock_range: .*\n\s+invoke-static/range \{p5 \.\. p6\}, "
                     r"Lseekpatch/Lock;->scene\(FF\)V\n\n\s+iput p7", stream)
    bar = text(tree, "Lfix/Stream$b;")
    assert re.search(r"invoke-static/range \{p3 \.\. p3\}, Lseekpatch/Lock;->bar\(Z\)Z\n\n\s+move-result p3\n\n\s+"
                     r"if-eqz p3, :cond_0\n", bar)
    assert re.search(r"->d:F\n\n\s+# seek-patch lock_range: .*\n\s+invoke-static/range \{v1 \.\. v1\}, "
                     r"Lseekpatch/Lock;->low\(F\)F\n\n\s+move-result v1\n(?:.*\n)*?.*->c:F\n\n\s+# seek-patch lock_range: .*\n\s+"
                     r"invoke-static/range \{v1 \.\. v1\}, Lseekpatch/Lock;->high\(F\)F\n\n\s+move-result v1\n", bar)
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch lock_range: .*\n\s+"
                     r"invoke-static \{p0\}, Lseekpatch/Lock;->attach\(Landroid/app/Activity;\)V\n", text(tree, "Lfix/Main;"))
    assert all(tree.path_of(f"Lseekpatch/{c};") for c in ("Lock", "Lock$1", "Lock$2", "Floating", "Floating$1"))
    assert not tree.path_of("Lseekpatch/SeekIP;")
    assert sorted(tree.natives) == ["lib/arm64-v8a/libseekpatch_lock.so", "lib/armeabi-v7a/libseekpatch_lock.so"]
    assert all(data[:4] == b"\x7fELF" for data in tree.natives.values())
    assert report[1].startswith("smali/fix/Stream.smali L()") and report[2].startswith("smali/fix/Stream$b.smali j()")
    assert report[-1] == "lib/{arm64-v8a,armeabi-v7a}/libseekpatch_lock.so"


def test_lock_range_composes_with_smart_smoothing(make_project):
    tree = tree_of(make_project, "lambda")
    smart_smoothing.apply(tree, Options())
    lock_range.apply(tree, Options())
    assert sorted(tree.natives) == ["lib/arm64-v8a/libseekpatch_lock.so", "lib/arm64-v8a/libseekpatch_smooth.so",
                                    "lib/armeabi-v7a/libseekpatch_lock.so", "lib/armeabi-v7a/libseekpatch_smooth.so"]
    pipeline = text(tree, "Lfix/Pipeline;")
    assert "Lseekpatch/Smooth;->frame()V" in pipeline and "Lseekpatch/Lock;->frame()V" in pipeline


def test_lock_range_library_exports_its_native_methods():
    from seekpatch import native
    for abi in native.ABIS:
        data = native.library(abi, native.LOCK)
        for name in (b"Java_seekpatch_Lock_install", b"Java_seekpatch_Lock_hold", b"Java_seekpatch_Lock_released"):
            assert name in data, (abi, name)


def test_lock_range_refuses_older_apps(make_project):
    tree = tree_of(make_project, "lambda")
    tree._identity = {"versionCode": 272, "versionName": "2.2.2"}
    with pytest.raises(PatchError, match="2.2.2"):
        lock_range.apply(tree, Options())


def test_lock_range_needs_an_arm_libseekip(make_project):
    tree = tree_of(make_project, "lambda", abis=("x86",))
    with pytest.raises(PatchError, match="no libseekip.so for arm64-v8a / armeabi-v7a"):
        lock_range.apply(tree, Options())


def test_lock_range_needs_one_results_method(make_project):
    root = make_project("lambda", ABIS)
    p = root / "smali" / "fix" / "Stream.smali"
    p.write_text(p.read_text() + "\n.method K(IIIIFFF)V\n    .locals 0\n\n    return-void\n.end method\n")
    with pytest.raises(PatchError, match=r"results \(IIIIFFF\)V, found 2"):
        lock_range.apply(SmaliTree(str(root)), Options())


def test_lock_range_needs_the_span_reads(make_project):
    root = make_project("lambda", ABIS)
    p = root / "smali" / "fix" / "Stream$b.smali"
    p.write_text(p.read_text().replace("iget v1, p0, Lfix/Stream$b;->c:F", "const/4 v1, 0x0"))
    tree = SmaliTree(str(root))
    before = dict(tree.files)
    with pytest.raises(PatchError, match="found 1 reads"):
        with tree.transaction():
            lock_range.apply(tree, Options())
    assert tree.files == before and tree.natives == {}


# calibration ------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_calibration(make_project, shape):
    tree = tree_of(make_project, shape)
    report = calibration.apply(tree, Options())
    assert re.search(r"Lfix/Pipeline;->set\(JLfix/Features;I\)V\n\n\s+# seek-patch calibration: .*\n\s+"
                     r"invoke-static \{\}, Lseekpatch/Calib;->frame\(\)V\n", text(tree, "Lfix/Pipeline;"))
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch calibration: .*\n\s+"
                     r"invoke-static \{p0\}, Lseekpatch/Calib;->attach\(Landroid/app/Activity;\)V\n", text(tree, "Lfix/Main;"))
    assert all(tree.path_of(f"Lseekpatch/{c};") for c in ("Calib", "Calib$1", "Floating", "Floating$1"))
    assert sorted(tree.natives) == ["lib/arm64-v8a/libseekpatch_calib.so", "lib/armeabi-v7a/libseekpatch_calib.so"]
    assert all(data[:4] == b"\x7fELF" for data in tree.natives.values())
    assert report == ["smali/fix/Pipeline.smali: Calib.frame after the feature-900 call",
                      "smali/fix/Main.smali: the button after Main.setContentView",
                      "lib/{arm64-v8a,armeabi-v7a}/libseekpatch_calib.so"]


def test_calibration_shares_the_floating_buttons_with_lock_range(make_project):
    tree = tree_of(make_project, "lambda")
    lock_range.apply(tree, Options())
    calibration.apply(tree, Options())
    assert sorted(tree.natives) == ["lib/arm64-v8a/libseekpatch_calib.so", "lib/arm64-v8a/libseekpatch_lock.so",
                                    "lib/armeabi-v7a/libseekpatch_calib.so", "lib/armeabi-v7a/libseekpatch_lock.so"]
    main = text(tree, "Lfix/Main;")
    assert "Lseekpatch/Lock;->attach" in main and "Lseekpatch/Calib;->attach" in main
    pipeline = text(tree, "Lfix/Pipeline;")
    assert "Lseekpatch/Lock;->frame()V" in pipeline and "Lseekpatch/Calib;->frame()V" in pipeline


def test_calibration_library_exports_its_native_methods():
    from seekpatch import native
    for abi in native.ABIS:
        data = native.library(abi, native.CALIB)
        for name in (b"Java_seekpatch_Calib_install", b"Java_seekpatch_Calib_set"):
            assert name in data, (abi, name)


def test_calibration_refuses_older_apps(make_project):
    tree = tree_of(make_project, "lambda")
    tree._identity = {"versionCode": 272, "versionName": "2.2.2"}
    with pytest.raises(PatchError, match="2.2.2"):
        calibration.apply(tree, Options())


def test_calibration_needs_an_arm_libseekip(make_project):
    tree = tree_of(make_project, "lambda", abis=("x86",))
    with pytest.raises(PatchError, match="no libseekip.so for arm64-v8a / armeabi-v7a"):
        calibration.apply(tree, Options())


# hidden_settings --------------------------------------------------------------------------------

HIDDEN = {"D": "allow_reg_optout_key", "E": "export_frame_rate_allowed_key", "I": "lossless_comp_allowed_key",
          "O": "sim_mode_allowed_key", "P": "staging_registration_allowed_key"}


@pytest.mark.parametrize("shape", SHAPES)
def test_hidden_settings(make_project, shape):
    tree = tree_of(make_project, shape)
    report = hidden_settings.apply(tree, Options())
    prefs = text(tree, "Lfix/Prefs;")
    for name in HIDDEN:
        body = next(m for m in methods(prefs) if m.name == name).body
        assert re.search(r"move-result p0\n\n\s+# seek-patch hidden_settings: always shown\n\s+const/4 p0, 0x1\n\n\s+"
                         r"return p0\n", body), name
    assert "seek-patch" not in next(m for m in methods(prefs) if m.name == "H").body  # the setting itself
    assert len(report) == 5 and report[0] == ("smali/fix/Prefs.smali I(): lossless_comp_allowed_key is true -- "
                                              "Save Uncompressed shown")
    with pytest.raises(AlreadyApplied):
        hidden_settings.apply(tree, Options())


def test_hidden_settings_leaves_save_uncompressed_to_png_photos(make_project):
    tree = tree_of(make_project, "lambda")
    png_photos.apply(tree, Options())
    report = hidden_settings.apply(tree, Options())
    body = next(m for m in methods(text(tree, "Lfix/Prefs;")) if m.name == "I").body
    assert re.search(r"move-result p0\n\n\s+# seek-patch hidden_settings: .*Android 11.*\n\s+"
                     r"sget p0, Landroid/os/Build\$VERSION;->SDK_INT:I\n\n\s+add-int/lit8 p0, p0, -0x1e\n\n\s+"
                     r"ushr-int/lit8 p0, p0, 0x1f\n\n\s+return p0\n", body)
    assert report[0].endswith("(before Android 11: png_photos forces it on from 11)")


def test_hidden_settings_takes_the_switches_there_are(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Prefs.smali"
    p.write_text(p.read_text().replace('"export_frame_rate_allowed_key"', '"other_key"'))
    report = hidden_settings.apply(SmaliTree(str(root)), Options())
    assert len(report) == 4 and not any("Show Frame Rate" in line for line in report)


def test_hidden_settings_needs_one_reader_per_switch(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Prefs.smali"
    p.write_text(p.read_text().replace('"export_frame_rate_allowed_key"', '"sim_mode_allowed_key"'))
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match="reader of sim_mode_allowed_key, found 2"):
        with tree.transaction():
            hidden_settings.apply(tree, Options())
    assert tree.save() == []


def test_hidden_settings_refuses_an_app_without_them(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Prefs.smali"
    text_ = p.read_text()
    for key in HIDDEN.values():
        text_ = text_.replace(f'"{key}"', '"other_key"')
    p.write_text(text_)
    with pytest.raises(PatchError, match="none of the hidden switches"):
        hidden_settings.apply(SmaliTree(str(root)), Options())


# fps_readout ------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_fps_readout(make_project, shape):
    tree = tree_of(make_project, shape)
    report = fps_readout.apply(tree, Options())
    meter = text(tree, "Lfix/Meter;")
    assert re.search(r"long-to-double v4, v4\n\n\s+# seek-patch fps_readout: .*\n\s+"
                     r"const-wide v6, 0x407f400000000000L    # 500\.0\n\n\s+cmpl-double v4, v4, v6\n", meter)
    assert "0x40a7700000000000L" not in meter and "const-wide v6, 0x408f400000000000L    # 1000.0" in meter
    assert report == ["smali/fix/Meter.smali frame(): the frame rate is recomputed every 500 ms instead of 3000"]
    with pytest.raises(AlreadyApplied):
        fps_readout.apply(tree, Options())


def test_fps_readout_one_second_window(make_project):  # 2.0.x: the window is the same 1000.0 as the divisor
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Meter.smali"
    p.write_text(p.read_text().replace("0x40a7700000000000L    # 3000.0", "0x408f400000000000L    # 1000.0"))
    tree = SmaliTree(str(root))
    report = fps_readout.apply(tree, Options())
    meter = text(tree, "Lfix/Meter;")
    assert meter.count("0x407f400000000000L") == 1 and meter.count("0x408f400000000000L") == 1
    assert report[0].endswith("every 500 ms instead of 1000")


def test_fps_readout_needs_the_counter(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Meter.smali"
    p.write_text(p.read_text().replace("cmpl-double v4, v4, v6", "cmpl-double v4, v6, v4"))
    with pytest.raises(PatchError, match="expected one frame counter"):
        fps_readout.apply(SmaliTree(str(root)), Options())


# shutter ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES)
def test_shutter(make_project, shape):
    tree = tree_of(make_project, shape)
    report = shutter.apply(tree, Options())
    usb = text(tree, "Lfix/Usb;")
    request = next(m for m in methods(usb) if m.name == "request")
    assert re.search(r"\.line 1\n\s+# seek-patch shutter: .*\n\s+invoke-static \{p1\}, "
                     r"Lseekpatch/Shutter;->transfer\(Landroid/hardware/usb/UsbDeviceConnection;\)V\n\n\s+const/4 v0, 0x4\n",
                     request.body)
    assert "seek-patch" not in next(m for m in methods(usb) if m.name == "mode").body
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch shutter: .*\n\s+"
                     r"invoke-static \{p0\}, Lseekpatch/Shutter;->attach\(Landroid/app/Activity;\)V\n", text(tree, "Lfix/Main;"))
    assert all(tree.path_of(f"Lseekpatch/{c};") for c in ("Shutter", "Shutter$1", "Floating"))
    assert tree.natives == {}
    assert report == ["smali/fix/Usb.smali request(): Shutter.transfer before the frame request",
                      "smali/fix/Main.smali: the button after Main.setContentView"]


def test_shutter_needs_one_frame_request(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "Usb.smali"
    p.write_text(p.read_text().replace("const/16 v3, 0x53", "const/16 v3, 0x37"))
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match=r"asking the camera for a frame \(request 0x53\), found 0"):
        with tree.transaction():
            shutter.apply(tree, Options())
    assert tree.save() == []


# smart_smoothing --------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_smart_smoothing(make_project, shape):
    tree = tree_of(make_project, shape)
    report = smart_smoothing.apply(tree, Options())
    assert re.search(r"Lfix/Pipeline;->set\(JLfix/Features;I\)V\n\n\s+# seek-patch smart_smoothing: .*\n\s+"
                     r"invoke-static \{\}, Lseekpatch/Smooth;->frame\(\)V\n", text(tree, "Lfix/Pipeline;"))
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch smart_smoothing: .*\n\s+"
                     r"invoke-static \{p0\}, Lseekpatch/Smooth;->attach\(Landroid/app/Activity;\)V\n",
                     text(tree, "Lfix/Main;"))
    assert all(tree.path_of(f"Lseekpatch/Smooth{s};") for s in ("", "$1", "$2", "$3"))
    assert sorted(tree.natives) == ["lib/arm64-v8a/libseekpatch_smooth.so", "lib/armeabi-v7a/libseekpatch_smooth.so"]
    assert report[-1] == "lib/{arm64-v8a,armeabi-v7a}/libseekpatch_smooth.so"


def test_smart_smoothing_writes_its_libraries_stored(make_project):
    root = make_project("lambda", ("arm64-v8a", "x86_64"))
    tree = SmaliTree(str(root))
    report = smart_smoothing.apply(tree, Options())
    assert report[-1] == "lib/{arm64-v8a}/libseekpatch_smooth.so (none for x86_64)"
    written = tree.save()
    assert "lib/arm64-v8a/libseekpatch_smooth.so" in written
    assert (root / "lib" / "arm64-v8a" / "libseekpatch_smooth.so").read_bytes()[:4] == b"\x7fELF"
    assert not (root / "lib" / "x86_64" / "libseekpatch_smooth.so").exists()
    assert "doNotCompress:\n- so\n- arsc\n" in (root / "apktool.yml").read_text()
    with pytest.raises(AlreadyApplied):
        smart_smoothing.apply(SmaliTree(str(root)), Options())


def test_smart_smoothing_composes_with_flat_field_and_no_smoothing(make_project):
    tree = tree_of(make_project, "lambda")
    no_smoothing.apply(tree, Options())
    flat_field.apply(tree, Options())
    smart_smoothing.apply(tree, Options())
    pipeline, main = text(tree, "Lfix/Pipeline;"), text(tree, "Lfix/Main;")
    assert "Lseekpatch/Flat;->frame(J)V" in pipeline and "Lseekpatch/Smooth;->frame()V" in pipeline
    assert "Lseekpatch/Flat;->attach(" in main and "Lseekpatch/Smooth;->attach(" in main


def test_smart_smoothing_rolls_back_its_libraries(make_project):
    root = make_project("lambda", ABIS)
    (root / "smali" / "fix" / "Main.smali").unlink()  # no camera activity: fails after finding the feature call
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match="setContentView"):
        with tree.transaction():
            smart_smoothing.apply(tree, Options())
    assert tree.natives == {} and tree.save() == []


def test_smart_smoothing_needs_an_arm_libseekip(make_project):
    with pytest.raises(PatchError, match="no libseekip.so for arm64-v8a / armeabi-v7a.*x86"):
        smart_smoothing.apply(tree_of(make_project, "lambda", ("x86",)), Options())
    with pytest.raises(PatchError, match="none"):
        smart_smoothing.apply(tree_of(make_project, "accessor", ()), Options())


def test_smart_smoothing_library_exports_every_native_method():
    from seekpatch import native
    from seekpatch.helpers import smali
    natives = re.findall(r"^\.method [^\n]*\bnative ([\w$]+)\(", smali("Smooth"), re.M)
    assert sorted(natives) == ["enable", "install", "setOptions"]
    for abi in native.ABIS:
        lib = native.library(abi)
        assert all(f"Java_seekpatch_Smooth_{n}".encode() + b"\0" in lib for n in natives), abi


def test_smart_smoothing_refuses_older_apps(make_project):
    tree = tree_of(make_project, "lambda")
    tree._identity = {"versionCode": 272, "versionName": "2.2.2"}
    with pytest.raises(PatchError, match="2.2.2"):
        smart_smoothing.apply(tree, Options())


# smoothing_settings -----------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["lambda", "accessor"])
def test_smoothing_settings(make_project, shape):
    tree = tree_of(make_project, shape)
    report = smoothing_settings.apply(tree, Options())
    pipeline = text(tree, "Lfix/Pipeline;")
    assert re.search(r"Lfix/Pipeline;->set\(JLfix/Features;I\)V\n\n\s+# seek-patch smoothing_settings: .*\n\s+"
                     r"invoke-static/range \{p0 \.\. p2\}, Lfix/Pipeline;->seekpatch_filters\(Lfix/Pipeline;J\)V\n", pipeline)
    helper = next(m for m in methods(pipeline) if m.name == "seekpatch_filters")
    assert "iget-boolean v0, p0, Lfix/Pipeline;->C:Z" in helper.body  # the value the 900 call sent
    assert "invoke-static {p1, p2, v0}, Lseekpatch/Filters;->frame(JZ)V" in helper.body
    # the settings hooks: after the Image & Video screen's preferences, and in the camera screen
    assert re.search(r"->addPreferencesFromResource\(I\)V\n\n\s+# seek-patch smoothing_settings: .*\n\s+"
                     r"invoke-static/range \{p0 \.\. p0\}, " + re.escape(SCREEN) + "\n", text(tree, "Lfix/ImageSettings;"))
    assert SCREEN not in text(tree, "Lfix/MainSettings;")
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch smoothing_settings: .*\n\s+"
                     r"invoke-static/range \{p0 \.\. p0\}, " + re.escape(ATTACH) + "\n", text(tree, "Lfix/Main;"))
    assert all(tree.path_of(c) for c in ("Lseekpatch/Filters;", "Lseekpatch/Settings;",
                                         "Lseekpatch/Settings$1;", "Lseekpatch/SeekIP;"))
    assert "Lfix/NativeLib;->g(JILjava/nio/ByteBuffer;I)I" in report[0]
    assert report[1] == "settings: ImageSettings.onCreate -> Settings.screen, Main.onCreate -> Settings.attach"


@pytest.mark.parametrize("order", [("smoothing_settings", "flat_field"), ("flat_field", "smoothing_settings")])
def test_smoothing_settings_shares_seekip_with_flat_field(make_project, order):
    tree = tree_of(make_project, "lambda")
    for name in order:
        BY_NAME[name].apply(tree, Options())
    pipeline = text(tree, "Lfix/Pipeline;")
    assert "Lseekpatch/Flat;->frame(J)V" in pipeline and "->seekpatch_filters(" in pipeline
    seekip = text(tree, "Lseekpatch/SeekIP;")
    assert f".source \"seek-patch {order[0]}\"" in seekip  # added once, by the first
    assert "invoke-static/range {p0 .. p4}, Lfix/NativeLib;->g(JILjava/nio/ByteBuffer;I)I" in seekip


@pytest.mark.parametrize("first, second", [(no_smoothing, smoothing_settings), (smoothing_settings, no_smoothing)])
def test_smoothing_settings_and_no_smoothing_are_alternatives(make_project, first, second):
    tree = tree_of(make_project, "lambda")
    first.apply(tree, Options())
    with pytest.raises(PatchError, match="alternatives"):
        second.apply(tree, Options())


def test_smoothing_settings_composes_with_smart_smoothing(make_project):
    tree = tree_of(make_project, "lambda")
    smoothing_settings.apply(tree, Options())
    smart_smoothing.apply(tree, Options())
    pipeline, main = text(tree, "Lfix/Pipeline;"), text(tree, "Lfix/Main;")
    assert "Lseekpatch/Smooth;->frame()V" in pipeline and "->seekpatch_filters(" in pipeline
    assert "Lseekpatch/Smooth;->attach(" in main and main.count(ATTACH) == 1


def test_smoothing_settings_refuses_older_apps(make_project):
    tree = tree_of(make_project, "lambda")
    tree._identity = {"versionCode": 250, "versionName": "2.1.7"}
    with pytest.raises(PatchError, match="2.1.7"):
        smoothing_settings.apply(tree, Options())


def test_smoothing_settings_needs_the_settings_screen(make_project):
    root = make_project("lambda")
    p = root / "smali" / "fix" / "ImageSettings.smali"
    p.write_text(p.read_text().replace('"use_smoothing"', '"show_temperature_bar"'))
    tree = SmaliTree(str(root))
    with pytest.raises(PatchError, match="Image & Video"):
        with tree.transaction():
            smoothing_settings.apply(tree, Options())
    assert tree.save() == []  # the feature hook found before it was rolled back


def test_smoothing_settings_needs_the_feature_call(make_project):
    with pytest.raises(PatchError, match="feature-900 call"):
        smoothing_settings.apply(tree_of(make_project, "virtual"), Options())


# all patches ------------------------------------------------------------------------------------

APPLICABLE = {  # every patch that applies, but no_smoothing (the alternative to smoothing_settings)
    "lambda": ["full_fps", "sharp_scaling", "smoothing_settings", "png_photos", "hidden_settings", "fps_readout",
               "photo_1x", "video_quality", "resume_fix", "reconnect_fix", "no_analytics", "http_legacy", "mic_prompt",
               "flat_field", "lock_range", "shutter", "calibration", "smart_smoothing", "debug_log"],
    "accessor": ["full_fps", "sharp_scaling", "smoothing_settings", "png_photos", "hidden_settings", "fps_readout",
                 "photo_1x", "video_quality", "resume_fix", "reconnect_fix", "no_analytics", "http_legacy",
                 "mic_prompt", "flat_field", "lock_range", "shutter", "calibration", "smart_smoothing", "debug_log"],
    "virtual": ["full_fps", "sharp_scaling", "png_photos", "hidden_settings", "fps_readout", "photo_1x",
                "reconnect_fix", "no_analytics", "http_legacy", "mic_prompt", "shutter", "debug_log"],
}


@pytest.mark.parametrize("shape", SHAPES)
def test_patches_compose_and_refuse_a_second_time(make_project, shape):
    tree = tree_of(make_project, shape)
    for name in APPLICABLE[shape]:
        BY_NAME[name].apply(tree, Options())
    for name in APPLICABLE[shape]:
        with pytest.raises(AlreadyApplied):
            BY_NAME[name].apply(tree, Options())


def test_a_failing_patch_leaves_the_tree_untouched(make_project):
    root = make_project("lambda")
    (root / "smali" / "fix" / "Pipeline.smali").unlink()  # no photo method: sharp_scaling fails after the shaders
    tree = SmaliTree(str(root))
    before = dict(tree.files)
    with pytest.raises(PatchError, match="photo method"):
        with tree.transaction():
            sharp_scaling.apply(tree, Options())
    assert tree.files == before
    assert tree.save() == []


def test_save_writes_only_changed_files(make_project):
    tree = tree_of(make_project, "lambda")
    full_fps.apply(tree, Options())
    assert tree.save() == ["smali/fix/Render.smali"]
