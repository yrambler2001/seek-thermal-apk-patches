from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SHAPES = ("lambda", "accessor", "virtual")


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
