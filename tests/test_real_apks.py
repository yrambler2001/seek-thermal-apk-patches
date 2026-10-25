"""Opt-in: run against real Seek Thermal apks and split bundles (.xapk / .apks / .apkm) you have
locally (not part of the repo).

    SEEK_APK_DIR=~/apks pytest tests/test_real_apks.py              # which patches apply, per version
    SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py # also build + sign every version

Expectations are the tested version ranges of each patch (patch.VERSIONS, docs/versions.md).
"""
from __future__ import annotations

import glob
import os
import zipfile

import pytest

from seekpatch import apk, zipalign
from seekpatch.patches import every_patch
from seekpatch.toolchain import Toolchain, ToolchainError

APK_DIR = os.environ.get("SEEK_APK_DIR")
APKS = sorted(p for ext in ("apk", "xapk", "apks", "apkm")
              for p in glob.glob(os.path.join(os.path.expanduser(APK_DIR), "*." + ext))) if APK_DIR else []

# first version each patch supports (all run through 2.3.4)
FIRST = {"full_fps": (1, 9, 1), "sharp_scaling": (2, 0), "debug_log": (2, 0), "no_smoothing": (2, 2, 0),
         "png_photos": (2, 1, 2), "photo_1x": (2, 1, 1), "video_quality": (2, 1, 2), "resume_fix": (1, 9, 1),
         "mic_prompt": (2, 3, 1), "flat_field": (2, 2, 0), "smart_smoothing": (2, 2, 3),
         "smoothing_settings": (2, 2, 0)}

pytestmark = pytest.mark.skipif(not APKS, reason="set SEEK_APK_DIR to a folder of Seek Thermal apks")


@pytest.fixture(scope="module")
def toolchain():
    try:
        return Toolchain.load(log=lambda _: None)
    except ToolchainError as e:
        pytest.skip(str(e))


def _version(path):
    name = apk.app_info(path).version_name or "0"
    return tuple(int(x) for x in name.split(".") if x.isdigit())


@pytest.mark.parametrize("path", APKS, ids=[os.path.basename(p) for p in APKS])
def test_patch_matrix(toolchain, path, tmp_path):
    info = apk.app_info(path)
    if info.package != apk.SEEK_PACKAGE:
        pytest.skip(f"not the Seek Thermal app: {info.package}")
    version = _version(path)
    results = apk.check(toolchain, path, log=lambda _: None)
    if any(why and "already applied" in why for why in results.values()):
        pytest.skip("an already patched apk")
    expected = {name: version >= first for name, first in FIRST.items()}
    assert {n: why is None for n, why in results.items()} == expected, results
    if os.environ.get("SEEK_BUILD"):
        out = str(tmp_path / "patched.apk")
        names = [n for n in every_patch() if expected.get(n)]  # not no_smoothing, the alternative
        apk.patch_apk(toolchain, path, out, apk.Plan(names), log=lambda _: None)
        assert zipalign.check(out) == []
        with zipfile.ZipFile(out) as z:
            libs = [i for i in z.infolist() if i.filename.endswith("/libseekpatch_smooth.so")]
            seekip = {n.split("/")[1] for n in z.namelist() if n.endswith("/libseekip.so")}
            dex = b"".join(z.read(n) for n in z.namelist() if n.startswith("classes") and n.endswith(".dex"))
        # each patch's settings, wherever it applies (the settings screen exists from 2.0 on)
        for patch, section in (("sharp_scaling", b"Lseekpatch/Upscale;"), ("video_quality", b"Lseekpatch/VideoSettings;"),
                               ("smoothing_settings", b"Lseekpatch/Filters;"), ("flat_field", b"Lseekpatch/FlatSettings;"),
                               ("photo_1x", b"Lseekpatch/PhotoSettings;")):
            assert (section in dex) == expected[patch], patch
        if expected["smart_smoothing"]:  # one per arm ABI the app ships, stored
            assert sorted(i.filename.split("/")[1] for i in libs) == sorted(seekip & {"arm64-v8a", "armeabi-v7a"})
            assert all(i.compress_type == zipfile.ZIP_STORED for i in libs)
        else:
            assert libs == []
