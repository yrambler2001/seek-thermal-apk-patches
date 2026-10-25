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

GAP = r"\n(?:[ \t]*(?:\.line \d+)?[ \t]*\n)*[ \t]*"
"""Between two consecutive instructions: the line break, any blank / .line lines, the indent."""


MANIFEST = "AndroidManifest.xml"


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


_TYPE = re.compile(r"\[*(?:L[^;]+;|[ZBSCIJFD])")
_DIRECTIVE = re.compile(r"[ \t]*(?:$|#|\.locals |\.registers |\.param |\.end param|\.prologue|\.line |\.source )")


def param_registers(m: Method) -> list[str]:
    """The p-register of each parameter, in order (this not included; long / double take two)."""
    sig = m.descriptor[m.descriptor.index("(") + 1:m.descriptor.index(")")]
    n = 0 if "static" in m.header.split() else 1
    out = []
    for t in _TYPE.findall(sig):
        out.append(f"p{n}")
        n += 2 if t in ("J", "D") else 1
    return out


def locals_count(body: str) -> int:
    m = re.search(r"^[ \t]*\.locals (\d+)$", body, re.M)
    if not m:
        raise PatchError("method without a .locals line")
    return int(m.group(1))


def register_number(reg: str, body: str) -> int:
    """v-number of a register (p registers follow the locals)."""
    return int(reg[1:]) + (locals_count(body) if reg[0] == "p" else 0)


def code_start(body: str) -> int:
    """Offset in a method body of its first instruction (after .locals, .param blocks, annotations)."""
    pos, in_annotation = 0, False
    for line in body.splitlines(keepends=True):
        s = line.strip()
        if in_annotation:
            in_annotation = s != ".end annotation"
        elif s.startswith(".annotation "):
            in_annotation = True
        elif not _DIRECTIVE.match(line):
            return pos
        pos += len(line)
    raise PatchError("method without instructions")


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
        self.natives: dict[str, bytes] = {}
        """Native libraries to add: path relative to the root (lib/<abi>/<name>.so) -> contents."""
        self._manifest: bytes | None = None
        self._manifest_dirty = False

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

    @property
    def abis(self) -> list[str]:
        """The ABIs the apk has native code for (lib/<abi>/ of the decoded tree)."""
        lib = os.path.join(self.root, "lib")
        if not os.path.isdir(lib):
            return []
        return sorted(d for d in os.listdir(lib) if os.path.isdir(os.path.join(lib, d)))

    def has_native(self, abi: str, name: str) -> bool:
        rel = f"lib/{abi}/{name}"
        return rel in self.natives or os.path.isfile(os.path.join(self.root, *rel.split("/")))

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

    @property
    def manifest(self) -> bytes:
        """AndroidManifest.xml as decoded: binary (apktool d -r, the default) or text (resources decoded)."""
        if self._manifest is None:
            with open(os.path.join(self.root, MANIFEST), "rb") as f:
                self._manifest = f.read()
        return self._manifest

    def set_manifest(self, data: bytes) -> None:
        if data != self.manifest:
            self._manifest = data
            self._manifest_dirty = True

    def add_native_library(self, abi: str, name: str, data: bytes) -> str:
        """A native library for lib/<abi>/, written by save() and stored uncompressed in the apk (the app
        maps its libraries straight out of it).  Returns its path relative to the root."""
        if self.has_native(abi, name):
            raise AlreadyApplied(f"lib/{abi}/{name} already exists")
        rel = f"lib/{abi}/{name}"
        self.natives[rel] = data
        return rel

    @contextlib.contextmanager
    def transaction(self):
        """Roll every edit back if the block raises: a failing patch leaves the tree untouched."""
        snapshot, natives = dict(self.files), dict(self.natives)
        dirty, created = set(self._dirty), set(self._created)
        manifest = self._manifest, self._manifest_dirty
        try:
            yield self
        except BaseException:
            self.files, self.natives, self._dirty, self._created = snapshot, natives, dirty, created
            self._manifest, self._manifest_dirty = manifest
            raise

    def save(self) -> list[str]:
        """Write the changed files; returns their paths relative to the root."""
        for p in sorted(self._dirty):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.files[p])
        written = sorted(self.rel(p) for p in self._dirty)
        self._dirty.clear()
        if self._manifest_dirty:
            with open(os.path.join(self.root, MANIFEST), "wb") as f:
                f.write(self._manifest)
            written.append(MANIFEST)
            self._manifest_dirty = False
        for rel, data in sorted(self.natives.items()):
            p = os.path.join(self.root, *rel.split("/"))
            if not os.path.exists(p):
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(data)
                written.append(rel)
        if self.natives:
            self._store_uncompressed("so")
        return written

    def _store_uncompressed(self, extension: str) -> None:
        """apktool b stores files whose extension apktool.yml lists under doNotCompress."""
        path = os.path.join(self.root, "apktool.yml")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"^doNotCompress:[ \t]*\n((?:-[^\n]*\n)*)", text, re.M)
        if m and re.search(r"^- " + re.escape(extension) + r"[ \t]*$", m.group(1), re.M):
            return
        if m:
            text = text[:m.start(1)] + f"- {extension}\n" + text[m.start(1):]
        else:
            text = text.rstrip("\n") + f"\ndoNotCompress:\n- {extension}\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
