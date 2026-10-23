"""Opt-in: run against real Seek Thermal apks you have locally (not part of the repo).

    SEEK_APK_DIR=~/apks pytest tests/test_real_apks.py              # which patches apply, per version
    SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py # also build + sign every version

Expectations are the tested version ranges of each patch (patch.VERSIONS, docs/versions.md).
"""
from __future__ import annotations

import glob
import os

import pytest

from seekpatch import apk, zipalign
from seekpatch.toolchain import Toolchain, ToolchainError

APK_DIR = os.environ.get("SEEK_APK_DIR")
APKS = sorted(glob.glob(os.path.join(os.path.expanduser(APK_DIR), "*.apk"))) if APK_DIR else []

# first version each patch supports (all run through 2.3.4)
FIRST = {"full_fps": (1, 9, 1), "sharp_scaling": (2, 0), "debug_log": (2, 0), "no_smoothing": (2, 2, 0),
         "png_photos": (2, 1, 2), "photo_1x": (2, 1, 1), "video_quality": (2, 1, 2), "resume_fix": (1, 9, 1)}

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
        names = [n for n, ok in expected.items() if ok]
        apk.patch_apk(toolchain, path, out, apk.Plan(names), log=lambda _: None)
        assert zipalign.check(out) == []
