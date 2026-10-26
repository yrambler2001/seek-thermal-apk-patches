from __future__ import annotations

import glob
import importlib.util
import os
import re

from seekpatch import __version__
from seekpatch.patches import ALL

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [os.path.join(REPO, name) for name in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md")] + \
    sorted(glob.glob(os.path.join(REPO, "docs", "*.md")))
LINK = re.compile(r"\]\(([^)\s]+)\)|\b(?:src|srcset)=\"([^\"]+)\"")


def _patch_index():
    spec = importlib.util.spec_from_file_location("patch_index", os.path.join(REPO, "tools", "patch_index.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_table_is_current():
    index = _patch_index()
    with open(index.INDEX, encoding="utf-8") as f:
        text = f.read()
    assert index.render(text) == text, "run tools/patch_index.py"


def test_readme_names_every_patch():
    with open(PAGES[0], encoding="utf-8") as f:
        text = f.read()
    assert [p.NAME for p in ALL if f"`{p.NAME}`" not in text] == []


def test_readme_names_the_output_of_this_version():
    with open(PAGES[0], encoding="utf-8") as f:
        text = f.read()
    assert f"_APKPure-patched-{__version__}.apk" in text, "the README's example output names an old version"


def test_local_links_resolve():
    missing = []
    for page in PAGES:
        with open(page, encoding="utf-8") as f:
            text = f.read()
        for m in LINK.finditer(text):
            target = (m.group(1) or m.group(2)).split("#")[0]
            if not target or re.match(r"[a-z]+:", target):
                continue
            if not os.path.exists(os.path.join(os.path.dirname(page), target)):
                missing.append(f"{os.path.relpath(page, REPO)}: {target}")
    assert missing == []
