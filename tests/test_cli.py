from __future__ import annotations

import pytest

from seekpatch import __version__
from seekpatch.cli import main
from seekpatch.patches import ALL, RECOMMENDED, conflicts, every_patch


def test_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for p in ALL:
        assert p.NAME in out and p.VERSIONS in out
    assert RECOMMENDED == ["full_fps", "default_palette", "sharp_scaling", "smoothing_settings", "png_photos",
                           "hidden_settings", "fps_readout", "photo_1x", "video_quality", "resume_fix", "mic_prompt", "flat_field", "lock_range",
                           "shutter", "calibration", "smart_smoothing"]


def test_all_leaves_out_the_alternative():
    assert every_patch() == RECOMMENDED + ["debug_log"]  # not no_smoothing
    assert conflicts(every_patch()) == []
    assert conflicts(["no_smoothing", "smoothing_settings", "flat_field"]) == [("no_smoothing", "smoothing_settings")]


def test_patch_refuses_alternatives(tmp_path):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match="alternatives"):
        main(["patch", str(f), "-p", "smoothing_settings", "-p", "no_smoothing"])


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_patch_missing_file():
    with pytest.raises(SystemExit, match="no such file"):
        main(["patch", "does-not-exist.apk"])


def test_patch_rejects_bad_sharpness(tmp_path):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match="sharpness"):
        main(["patch", str(f), "--sharpness", "1"])


@pytest.mark.parametrize("args, match", [(["--video-qp", "5"], "video-qp"), (["--video-qp", "50"], "video-qp")])
def test_patch_rejects_bad_video_options(tmp_path, args, match):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match=match):
        main(["patch", str(f), *args])


def test_patch_unknown_name():
    with pytest.raises(SystemExit):
        main(["patch", "x.apk", "-p", "nope"])


def test_package_needs_side_by_side(tmp_path):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match="side-by-side"):
        main(["patch", str(f), "--label", "Mine"])
