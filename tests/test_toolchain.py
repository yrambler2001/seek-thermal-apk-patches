from __future__ import annotations

import sys

import pytest

from seekpatch import toolchain


@pytest.fixture
def data(tmp_path, monkeypatch):
    """The per-user folders under tmp_path (Linux layout)."""
    monkeypatch.delenv("SEEK_PATCH_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    return tmp_path


def test_home_moves_the_folder_from_before_the_rename(data, capsys):
    old = data / "seek-patch"
    (old / "tools").mkdir(parents=True)
    (old / "signing-key.jks").write_bytes(b"key")
    new = data / "seek-thermal-apk-patches"
    assert toolchain.home() == str(new)
    assert (new / "signing-key.jks").read_bytes() == b"key" and (new / "tools").is_dir()
    assert not old.exists()
    assert f"moved {old} to {new}" in capsys.readouterr().err
    assert toolchain.home() == str(new)
    assert capsys.readouterr().err == ""  # once


def test_home_leaves_the_old_folder_when_the_new_one_exists(data):
    for name, key in (("seek-patch", b"old"), ("seek-thermal-apk-patches", b"new")):
        (data / name).mkdir()
        (data / name / "signing-key.jks").write_bytes(key)
    assert toolchain.home() == str(data / "seek-thermal-apk-patches")
    assert (data / "seek-patch" / "signing-key.jks").read_bytes() == b"old"
    assert (data / "seek-thermal-apk-patches" / "signing-key.jks").read_bytes() == b"new"


def test_home_on_a_new_install(data):
    assert toolchain.home() == str(data / "seek-thermal-apk-patches")
    assert list(data.iterdir()) == []  # made when there is something to keep


def test_home_from_the_environment(data, monkeypatch):
    (data / "seek-patch").mkdir()
    monkeypatch.setenv("SEEK_PATCH_HOME", str(data / "elsewhere"))
    assert toolchain.home() == str(data / "elsewhere")
    assert (data / "seek-patch").is_dir()  # not moved
