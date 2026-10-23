"""The patched fixtures assemble (apktool b) and go through align + sign, and the whole pipeline --
check, patch, --side-by-side, a split bundle -- runs on an apk built from them.  Needs Java and the
pinned jars in the cache (`seek-patch doctor`); skipped otherwise, unless SEEK_PATCH_REQUIRE_TOOLS is
set (CI)."""
from __future__ import annotations

import os
import zipfile

import pytest
from conftest import SHAPES, split_apk
from test_patches import APPLICABLE

from seekpatch import apk, zipalign
from seekpatch.smali import PatchError
from seekpatch.toolchain import Toolchain, ToolchainError

QUIET = lambda _: None  # noqa: E731


def _skip_without(e: ToolchainError):
    if os.environ.get("SEEK_PATCH_REQUIRE_TOOLS"):
        raise e
    pytest.skip(f"no toolchain: {e}")


@pytest.fixture(scope="session")
def toolchain():
    try:
        return Toolchain.load(download=bool(os.environ.get("SEEK_PATCH_DOWNLOAD")), log=QUIET)
    except ToolchainError as e:
        _skip_without(e)


@pytest.fixture(scope="session")
def merger(toolchain):
    try:
        return toolchain.merger(log=QUIET)
    except ToolchainError as e:
        _skip_without(e)


@pytest.mark.parametrize("shape", SHAPES)
def test_patched_fixture_assembles_and_signs(make_project, toolchain, tmp_path, shape):
    root = make_project(shape)
    assert apk.apply_patches(str(root), apk.Plan(APPLICABLE[shape]), log=QUIET) == APPLICABLE[shape]
    unsigned, signed = str(tmp_path / "unsigned.apk"), str(tmp_path / "signed.apk")
    apk.build(toolchain, str(root), unsigned)
    apk.sign(toolchain, unsigned, signed, log=QUIET)
    with zipfile.ZipFile(signed) as z:
        names = z.namelist()
        assert "classes.dex" in names and "AndroidManifest.xml" in names
        assert any(n.startswith("META-INF/") and n.endswith(".SF") for n in names)  # v1 signature
        assert b"Lseekpatch/SharpScale;" in z.read("classes.dex")
    assert zipalign.check(signed) == []
    info = apk.app_info(signed)
    assert (info.package, info.version_name, info.version_code) == ("org.example.seekfixture", "2.3.4", 294)


@pytest.fixture
def fixture_apk(make_project, toolchain, tmp_path):
    """fixture_apk(shape, with_lib=True) -> an unpatched apk built from a fixture tree."""

    def make(shape: str, with_lib: bool = True) -> str:
        root = make_project(shape)
        if with_lib:  # the fixture's NativeLib loads "seekip"
            (root / "lib" / "arm64-v8a").mkdir(parents=True)
            (root / "lib" / "arm64-v8a" / "libseekip.so").write_bytes(b"\x7fELF" + bytes(60))
        out = str(tmp_path / f"{shape}.apk")
        apk.build(toolchain, str(root), out)
        return out

    return make


def test_check_reports_each_patch(fixture_apk, toolchain):
    results = apk.check(toolchain, fixture_apk("virtual"), log=QUIET)
    assert results["full_fps"] is None and results["sharp_scaling"] is None and results["debug_log"] is None
    assert "feature-900 call" in results["no_smoothing"]
    assert "(apk)" not in results


def test_check_flags_a_split_base_apk(fixture_apk, toolchain):
    results = apk.check(toolchain, fixture_apk("lambda", with_lib=False), log=QUIET)
    assert "libseekip.so" in results["(apk)"]


def test_patch_default_set_skips_what_does_not_apply(fixture_apk, toolchain, tmp_path):
    out, lines = str(tmp_path / "out.apk"), []
    plan = apk.Plan(["full_fps", "sharp_scaling", "no_smoothing"], skip_unavailable=True)
    apk.patch_apk(toolchain, fixture_apk("virtual"), out, plan, log=lines.append)
    assert any(line.startswith("skip   no_smoothing") for line in lines)
    assert zipalign.check(out) == [] and apk.app_info(out).package == "org.example.seekfixture"


def test_patch_named_patches_must_apply(fixture_apk, toolchain, tmp_path):
    with pytest.raises(PatchError, match="feature-900"):
        apk.patch_apk(toolchain, fixture_apk("virtual"), str(tmp_path / "out.apk"), apk.Plan(["no_smoothing"]), log=QUIET)


def test_patch_refuses_a_split_base_apk(fixture_apk, toolchain, tmp_path):
    with pytest.raises(apk.ApkError, match="split install"):
        apk.patch_apk(toolchain, fixture_apk("lambda", with_lib=False), str(tmp_path / "out.apk"),
                      apk.Plan(["full_fps"]), log=QUIET)


def test_side_by_side(fixture_apk, toolchain, tmp_path):
    out = str(tmp_path / "out.apk")
    plan = apk.Plan(["full_fps", "sharp_scaling"], side_by_side=True, label="Seek (patched)")
    apk.patch_apk(toolchain, fixture_apk("lambda"), out, plan, log=QUIET)
    info = apk.app_info(out)
    assert (info.package, info.version_name, info.version_code) == ("org.example.seekfixture.patched", "2.3.4", 294)
    assert zipalign.check(out) == []


@pytest.fixture
def fixture_bundle(fixture_apk, tmp_path):
    """fixture_bundle(with_lib=True) -> an .xapk of the fixture's base apk and its arm64 split."""

    def make(with_lib: bool = True) -> str:
        path = str(tmp_path / "app.xapk")
        with zipfile.ZipFile(path, "w") as z:
            z.write(fixture_apk("lambda", with_lib=False), "org.example.seekfixture.apk")
            z.writestr("config.arm64_v8a.apk", split_apk(with_lib))
            z.writestr("manifest.json", "{}")
        return path

    return make


def test_patch_a_split_bundle(fixture_bundle, toolchain, merger, tmp_path):
    path = fixture_bundle()
    results = apk.check(toolchain, path, log=QUIET)
    assert "(apk)" not in results and results["full_fps"] is None
    out, lines = str(tmp_path / "out.apk"), []
    apk.patch_apk(toolchain, path, out, apk.Plan(["full_fps"]), log=lines.append)
    assert "merge  app.xapk: base + 1 split (arm64_v8a), with APKEditor" in lines
    with zipfile.ZipFile(out) as z:
        assert z.getinfo("lib/arm64-v8a/libseekip.so").compress_type == zipfile.ZIP_STORED
    assert zipalign.check(out) == []
    info = apk.app_info(out)
    assert (info.package, info.version_name, info.version_code) == ("org.example.seekfixture", "2.3.4", 294)


def test_patch_refuses_a_bundle_without_native_code(fixture_bundle, toolchain, merger, tmp_path):
    with pytest.raises(apk.ApkError, match="no split with libseekip.so"):
        apk.patch_apk(toolchain, fixture_bundle(with_lib=False), str(tmp_path / "out.apk"), apk.Plan(["full_fps"]),
                      log=QUIET)
