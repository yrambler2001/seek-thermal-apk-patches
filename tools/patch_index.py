#!/usr/bin/env python3
"""Write the patch table of docs/README.md from the patches' NAME, SUMMARY, VERSIONS and RECOMMENDED,
between its <!-- patches --> markers (--check: is it up to date).  tests/test_docs.py runs the check.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

from seekpatch.patches import ALL  # noqa: E402

INDEX = os.path.join(REPO, "docs", "README.md")
START = "<!-- patches: written by tools/patch_index.py from the patch modules, do not edit -->"
END = "<!-- /patches -->"


def doc(name: str) -> str:
    return name.replace("_", "-") + ".md"


def prose(text: str) -> str:
    """The terminal's ASCII as Markdown: arrows, and en dashes in ranges."""
    return re.sub(r"(\d) - (\d)", "\\1 – \\2", text.replace(" -> ", " → "))


def table() -> str:
    rows = ["| patch | what it does | versions | default |", "|---|---|---|:---:|"]
    for p in ALL:
        rows.append(f"| [`{p.NAME}`]({doc(p.NAME)}) | {prose(p.SUMMARY)} | {prose(p.VERSIONS)} | "
                    f"{'✓' if p.RECOMMENDED else 'opt-in'} |")
    return "\n".join(rows)


def render(text: str) -> str:
    """text with the part between the markers replaced by the current table."""
    start, end = text.index(START) + len(START), text.index(END)
    return text[:start] + "\n" + table() + "\n" + text[end:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if docs/README.md's table is stale")
    a = ap.parse_args()
    with open(INDEX, encoding="utf-8") as f:
        text = f.read()
    new = render(text)
    if a.check:
        if new != text:
            print("docs/README.md: the patch table is stale; run tools/patch_index.py", file=sys.stderr)
            return 1
        return 0
    if new != text:
        with open(INDEX, "w", encoding="utf-8") as f:
            f.write(new)
        print("docs/README.md: patch table written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
