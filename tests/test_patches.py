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
    full_fps,
    no_smoothing,
    png_photos,
    sharp_scaling,
)
from seekpatch.smali import AlreadyApplied, PatchError, SmaliTree, methods


def tree_of(make_project, shape: str) -> SmaliTree:
    return SmaliTree(str(make_project(shape)))


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


# all patches ------------------------------------------------------------------------------------

APPLICABLE = {
    "lambda": ["full_fps", "sharp_scaling", "no_smoothing", "png_photos", "debug_log"],
    "accessor": ["full_fps", "sharp_scaling", "no_smoothing", "png_photos", "debug_log"],
    "virtual": ["full_fps", "sharp_scaling", "png_photos", "debug_log"],
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
