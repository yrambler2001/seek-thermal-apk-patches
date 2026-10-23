"""Reading and editing an apktool smali tree.

The Seek app is obfuscated and every release renames its classes, so patches never hardcode a class
name: they find code by what it does (a string it names, an API it calls, a call shape) and edit the
text in place.  This module holds the shared plumbing: a tree of smali files with transactional
edits, method iteration, and the register/string helpers the patches share.
"""
from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass

from .axml import decoded_identity

REG = r"[vp]\d+"
"""A smali register (v0, p1, ...)."""


class PatchError(Exception):
    """A patch could not find, or could not safely change, the code it targets."""


class AlreadyApplied(PatchError):
    """The tree already carries this patch."""


@dataclass
class Method:
    header: str  # text after ".method ", e.g. "private declared-synchronized i(Ljava/nio/ByteBuffer;II)V"
    body: str    # everything between the header line and ".end method"
    start: int   # offset of ".method" in the file
    end: int     # offset just past ".end method"

    @property
    def name(self) -> str:
        return re.search(r"([\w$<>-]+)\(", self.header).group(1)

    @property
    def descriptor(self) -> str:
        """name + signature, e.g. "i(Ljava/nio/ByteBuffer;II)V" """
        return self.header[self.header.index(self.name + "("):]

    @property
    def is_static_synthetic(self) -> bool:
        words = self.header.split()
        return "static" in words and "synthetic" in words

    @property
    def is_private(self) -> bool:
        return "private" in self.header.split()


_METHOD = re.compile(r"^\.method ([^\n]*)\n(.*?)^\.end method", re.S | re.M)
_CLASS = re.compile(r"^\.class [^\n]*?(L[\w/$-]+;)$", re.M)


def methods(text: str) -> Iterator[Method]:
    for m in _METHOD.finditer(text):
        yield Method(m.group(1), m.group(2), m.start(), m.end())


def method_at(text: str, pos: int) -> Method | None:
    """The method that contains offset pos."""
    for m in methods(text):
        if m.start <= pos < m.end:
            return m
    return None


def class_descriptor(text: str) -> str:
    m = _CLASS.search(text)
    if not m:
        raise PatchError("smali file without a .class line")
    return m.group(1)


def const_strings(text: str) -> Iterator[re.Match]:
    """const-string instructions; group(1) is the literal as written in smali (escapes kept)."""
    return re.finditer(r'const-string(?:/jumbo)? ' + REG + r', "((?:[^"\\]|\\.)*)"', text)


def smali_escape(s: str) -> str:
    """Text -> smali string-literal body (newlines, quotes, backslashes)."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class SmaliTree:
    """All smali files of a decoded apk, loaded once, edited in memory, written by save()."""

    def __init__(self, root: str):
        self.root = root
        self.dirs = sorted(d for d in os.listdir(root) if d.startswith("smali") and os.path.isdir(os.path.join(root, d)))
        if not self.dirs:
            raise PatchError(f"no smali directories in {root}")
        self.files: dict[str, str] = {}
        for d in self.dirs:
            for dirpath, _, names in os.walk(os.path.join(root, d)):
                for n in names:
                    if n.endswith(".smali"):
                        p = os.path.join(dirpath, n)
                        with open(p, encoding="utf-8") as f:
                            self.files[p] = f.read()
        self._dirty: set[str] = set()
        self._created: set[str] = set()
        self._identity: dict[str, object] | None = None

    # -- lookup -------------------------------------------------------------------------------
    @property
    def identity(self) -> dict[str, object]:
        """package / versionCode / versionName of the decoded app ({} if unknown)."""
        if self._identity is None:
            self._identity = decoded_identity(self.root)
        return self._identity

    @property
    def version(self) -> tuple[int, ...] | None:
        """versionName as numbers, e.g. (2, 3, 4)."""
        name = self.identity.get("versionName")
        m = re.match(r"[\d.]+", str(name)) if name else None
        return tuple(int(x) for x in m.group(0).split(".") if x) if m else None

    @property
    def version_code(self) -> int | None:
        code = self.identity.get("versionCode")
        return code if isinstance(code, int) else None

    def containing(self, *needles: str) -> list[str]:
        """Paths of files that contain every needle."""
        return [p for p, t in self.files.items() if all(n in t for n in needles)]

    def path_of(self, descriptor: str) -> str | None:
        """Lcom/foo/Bar; -> path of its smali file (any smali* dir)."""
        rel = (descriptor[1:-1] + ".smali").replace("/", os.sep)
        for d in self.dirs:
            p = os.path.join(self.root, d, rel)
            if p in self.files:
                return p
        return None

    def rel(self, path: str) -> str:
        """Path relative to the tree root, with forward slashes on every OS."""
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    # -- editing ------------------------------------------------------------------------------
    def get(self, path: str) -> str:
        return self.files[path]

    def set(self, path: str, text: str) -> None:
        if self.files.get(path) != text:
            self.files[path] = text
            self._dirty.add(path)

    def replace_method_body(self, path: str, method: Method, new_body: str) -> None:
        text = self.files[path]
        head_end = text.index("\n", method.start) + 1
        if text[head_end:method.end - len(".end method")] != method.body:
            raise PatchError(f"{self.rel(path)}: {method.name} changed underneath the patch")
        self.set(path, text[:head_end] + new_body + text[method.end - len(".end method"):])

    def add_class(self, descriptor: str, text: str) -> str:
        """A new class file in the first smali dir (the primary dex)."""
        if self.path_of(descriptor):
            raise AlreadyApplied(f"{descriptor} already exists")
        p = os.path.join(self.root, self.dirs[0], (descriptor[1:-1] + ".smali").replace("/", os.sep))
        self.files[p] = text
        self._dirty.add(p)
        self._created.add(p)
        return p

    @contextlib.contextmanager
    def transaction(self):
        """Roll every edit back if the block raises: a failing patch leaves the tree untouched."""
        snapshot = dict(self.files)
        dirty, created = set(self._dirty), set(self._created)
        try:
            yield self
        except BaseException:
            self.files, self._dirty, self._created = snapshot, dirty, created
            raise

    def save(self) -> list[str]:
        """Write the changed files; returns their paths relative to the root."""
        for p in sorted(self._dirty):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.files[p])
        written = sorted(self.rel(p) for p in self._dirty)
        self._dirty.clear()
        return written
