from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SHAPES = ("lambda", "accessor", "virtual")


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_STORED if name.endswith(".so") else zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def split_apk(with_lib: bool = True, manifest: bytes | None = None) -> bytes:
    """The fixture app's config.arm64_v8a split, with the native library its code loads."""
    entries = {"AndroidManifest.xml": manifest or (FIXTURES / "split" / "AndroidManifest.xml").read_bytes()}
    if with_lib:
        entries["lib/arm64-v8a/libseekip.so"] = b"\x7fELF" + bytes(60)
    return zip_bytes(entries)


@pytest.fixture
def make_project(tmp_path):
    """make_project(shape) -> an apktool -r style project with the shape's smali tree."""

    def make(shape: str) -> Path:
        root = tmp_path / shape
        shutil.copytree(FIXTURES / "project", root)
        shutil.copytree(FIXTURES / "common", root / "smali")
        shutil.copytree(FIXTURES / shape, root / "smali", dirs_exist_ok=True)
        return root

    return make
