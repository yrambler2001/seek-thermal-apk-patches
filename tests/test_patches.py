"""Every patch against the synthetic smali trees (tests/fixtures): what it changes, and that it
refuses -- without touching anything -- when the code is not there."""
from __future__ import annotations

import re

import pytest
from conftest import SHAPES

from seekpatch.patches import (
    BY_NAME,
    Options,
    debug_log,
    flat_field,
    full_fps,
    mic_prompt,
    no_smoothing,
    photo_1x,
    png_photos,
    resume_fix,
    sharp_scaling,
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
    assert "(t - i - 0.5) * 2.0000 + 0.5" in program
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
    assert "const/16 v5, 2" in helper and "glUniform2f" in helper


def test_sharp_scaling_sharpness_is_configurable(make_project):
    tree = tree_of(make_project, "lambda")
    report = sharp_scaling.apply(tree, Options(sharpness=3.5))
    assert "* 3.5000 + 0.5" in text(tree, "Lfix/Program;")
    assert "const/16 v5, 4" in text(tree, "Lseekpatch/SharpScale;")  # photo path rounds to an integer factor
    assert report[0].startswith("sharpness 3.5")


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
    photo_1x.apply(tree, Options())
    pipeline = text(tree, "Lfix/Pipeline;")
    e0 = next(m for m in methods(pipeline) if m.name == "e0")
    assert re.search(r"\.locals 5\n\n\s+# seek-patch photo_1x[^\n]*\n\s+iget-object v0, p0, Lfix/Pipeline;->ctx:"
                     r"Landroid/content/Context;\n\s+invoke-static \{v0, p2\}, Lseekpatch/Photo1x;->capture\("
                     r"Landroid/content/Context;Landroid/graphics/Bitmap;\)V\n\n\s+new-instance v0", e0.body)
    exif = next(m for m in methods(pipeline) if m.name == "T")
    assert re.search(r"invoke-static \{\}, Lfix/Pipeline;->o0\(\)I\n\s+move-result v0\n\s+invoke-static \{p2, v0\}, "
                     r"Lseekpatch/Photo1x;->saved\(Ljava/io/File;I\)V\n\n\s+return-void", exif.body)
    assert tree.path_of("Lseekpatch/Photo1x;")


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
    assert re.search(r"->setContentView\(I\)V\n\n\s+# seek-patch flat_field: .*\n\s+"
                     r"invoke-static \{p0\}, Lseekpatch/Flat;->attach\(Landroid/app/Activity;\)V\n", text(tree, "Lfix/Main;"))
    seekip = text(tree, "Lseekpatch/SeekIP;")
    assert "invoke-static/range {p0 .. p4}, Lfix/NativeLib;->c(JILjava/nio/ByteBuffer;I)I" in seekip
    assert "invoke-static/range {p0 .. p4}, Lfix/NativeLib;->g(JILjava/nio/ByteBuffer;I)I" in seekip
    assert all(tree.path_of(f"Lseekpatch/Flat{s};") for s in ("", "$1", "$2", "$3", "$4", "$5"))
    assert "Lfix/NativeLib;->c(" in report[0]


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
    assert all(tree.path_of(c) for c in ("Lseekpatch/Filters;", "Lseekpatch/Filters$1;", "Lseekpatch/Settings;",
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
    "lambda": ["full_fps", "sharp_scaling", "smoothing_settings", "png_photos", "photo_1x", "video_quality",
               "resume_fix", "mic_prompt", "flat_field", "smart_smoothing", "debug_log"],
    "accessor": ["full_fps", "sharp_scaling", "smoothing_settings", "png_photos", "photo_1x", "video_quality",
                 "resume_fix", "mic_prompt", "flat_field", "smart_smoothing", "debug_log"],
    "virtual": ["full_fps", "sharp_scaling", "png_photos", "photo_1x", "mic_prompt", "debug_log"],
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
