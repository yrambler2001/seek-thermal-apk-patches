from __future__ import annotations

import pytest

from seekpatch import __version__
from seekpatch.cli import main
from seekpatch.patches import ALL, RECOMMENDED


def test_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for p in ALL:
        assert p.NAME in out and p.VERSIONS in out
    assert RECOMMENDED == ["full_fps", "sharp_scaling", "no_smoothing"]


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


def test_patch_unknown_name():
    with pytest.raises(SystemExit):
        main(["patch", "x.apk", "-p", "nope"])


def test_package_needs_side_by_side(tmp_path):
    f = tmp_path / "x.apk"
    f.write_bytes(b"")
    with pytest.raises(SystemExit, match="side-by-side"):
        main(["patch", str(f), "--label", "Mine"])
