from __future__ import annotations

import pytest

from seekpatch import NAME, __version__
from seekpatch.cli import default_out, main
from seekpatch.patches import ALL, RECOMMENDED, every_patch


def test_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for p in ALL:
        assert p.NAME in out and p.VERSIONS in out
    assert RECOMMENDED == ["full_fps", "steady_fps", "default_palette", "default_unit", "sharp_scaling", "smoothing_settings", "png_photos",
                           "hidden_settings", "language", "fps_readout", "photo_1x", "video_quality", "phone_camera", "resume_fix", "reconnect_fix", "usb_prompt", "relaunch_fix", "no_analytics", "http_legacy", "mic_prompt", "flat_field", "lock_range",
                           "shutter", "calibration", "smart_smoothing"]


def test_all_is_the_default_set_and_debug_log():
    assert every_patch() == RECOMMENDED + ["debug_log"]


def test_patch_refuses_a_missing_requirement(tmp_path):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match="phone_camera needs video_quality: add it"):
        main(["patch", str(f), "-p", "full_fps", "-p", "phone_camera"])


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.strip() == f"{NAME} {__version__}"


def test_the_output_is_named_after_the_input_and_the_version():
    assert default_out("dl/Seek Thermal_2.3.4.xapk", False) == f"dl/Seek Thermal_2.3.4-patched-{__version__}.apk"
    assert default_out("Seek.apk", True) == f"Seek-patched-{__version__}-side-by-side.apk"


def test_patch_missing_file():
    with pytest.raises(SystemExit, match="no such file"):
        main(["patch", "does-not-exist.apk"])


@pytest.mark.parametrize("args, match", [
    (["--sharpness", "3"], "--sharpness was removed in 1.0: the build starts at Sharp 2, as iOS; pick Upscaling"),
    (["--sharpness=3"], "--sharpness was removed"),
    (["--video-codec", "avc"], "--video-codec was removed in 1.0: the build starts at H.265; pick Video codec"),
    (["--video-qp", "24"], "--video-qp was removed in 1.0: the build starts at QP 18; pick Video quality"),
    (["-p", "no_smoothing"], "no_smoothing was removed in 1.0: smoothing_settings"),
    (["--patch=no_smoothing"], "no_smoothing was removed"),
])
def test_patch_names_what_replaced_a_removed_option(args, match):
    with pytest.raises(SystemExit, match=match):
        main(["patch", "x.apk", *args])


def test_patch_unknown_name():
    with pytest.raises(SystemExit):
        main(["patch", "x.apk", "-p", "nope"])


def test_package_needs_side_by_side(tmp_path):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match="side-by-side"):
        main(["patch", str(f), "--label", "Mine"])
