"""Just enough of Android's binary resource formats to read an apk's identity -- the <manifest>
element of the binary AndroidManifest.xml (package, versionCode, versionName) and, when versionName
is a string resource, its value from resources.arsc -- without decoding the whole app; to count the
strings of each language in resources.arsc (string_locales); and to add an element to a binary
manifest (Document, add_uses_library)."""
from __future__ import annotations

import os
import re
import struct
import zipfile

_STRING_POOL, _RESOURCE_MAP, _START_ELEMENT = 0x0001, 0x0180, 0x0102
_UTF8 = 1 << 8
_NO_STRING = 0xFFFFFFFF
_TYPE_REFERENCE, _TYPE_STRING, _TYPE_INT_DEC, _TYPE_INT_HEX = 0x01, 0x03, 0x10, 0x11
VERSION_CODE, VERSION_NAME = 0x0101021B, 0x0101021C  # android:versionCode / android:versionName


class AxmlError(Exception):
    pass


class Reference(int):
    """A resource id an attribute points at (@string/...)."""


def _strings(buf: bytes, chunk: int) -> list[str]:
    count, _styles, flags, start = struct.unpack_from("<IIII", buf, chunk + 8)
    offsets = struct.unpack_from(f"<{count}I", buf, chunk + 28)
    base = chunk + start
    out = []
    for off in offsets:
        p = base + off
        if flags & _UTF8:
            n = buf[p]
            p += 2 if n & 0x80 else 1           # character count (unused)
            n = buf[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | buf[p + 1]
                p += 2
            else:
                p += 1
            out.append(buf[p:p + n].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", buf, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", buf, p)[0]
                p += 2
            out.append(buf[p:p + 2 * n].decode("utf-16-le", "replace"))
    return out


def manifest_attributes(buf: bytes) -> dict[str, object]:
    """Attributes of the first <manifest> element: 'package', 'versionCode', 'versionName'."""
    try:
        return _manifest_attributes(buf)
    except (struct.error, IndexError, UnicodeError) as e:
        raise AxmlError(f"corrupt binary manifest ({e})") from None


def _manifest_attributes(buf: bytes) -> dict[str, object]:
    if len(buf) < 8 or struct.unpack_from("<H", buf, 0)[0] != 0x0003:
        raise AxmlError("not a binary XML file")
    pos = struct.unpack_from("<H", buf, 2)[0]
    strings: list[str] = []
    resmap: tuple[int, ...] = ()
    while pos + 8 <= len(buf):
        ctype, header, size = struct.unpack_from("<HHI", buf, pos)
        if size < 8:
            raise AxmlError("corrupt chunk")
        if ctype == _STRING_POOL:
            strings = _strings(buf, pos)
        elif ctype == _RESOURCE_MAP:
            resmap = struct.unpack_from(f"<{(size - header) // 4}I", buf, pos + header)
        elif ctype == _START_ELEMENT:
            _ns, name, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", buf, pos + 16)
            if strings[name] != "manifest":
                raise AxmlError(f"first element is <{strings[name]}>, not <manifest>")
            out: dict[str, object] = {}
            for i in range(attr_count):
                a = pos + 16 + attr_start + i * attr_size
                _ans, aname, raw, _vsize, _res0, vtype, data = struct.unpack_from("<IIIHBBI", buf, a)
                rid = resmap[aname] if aname < len(resmap) else 0
                key = {VERSION_CODE: "versionCode", VERSION_NAME: "versionName"}.get(rid, strings[aname])
                if vtype in (_TYPE_INT_DEC, _TYPE_INT_HEX):
                    out[key] = data
                elif raw != _NO_STRING:
                    out[key] = strings[raw]
                elif vtype == _TYPE_STRING:
                    out[key] = strings[data]
                elif vtype == _TYPE_REFERENCE:
                    out[key] = Reference(data)  # e.g. versionName="@string/app_version"
            return out
        pos += size
    raise AxmlError("no <manifest> element")


_TABLE, _PACKAGE, _TYPE = 0x0002, 0x0200, 0x0201
_FLAG_SPARSE, _FLAG_OFFSET16 = 0x01, 0x02
_ENTRY_COMPLEX, _ENTRY_COMPACT = 0x0001, 0x0008
_NO_ENTRY, _NO_ENTRY16 = 0xFFFFFFFF, 0xFFFF


def resolve_string(arsc: bytes, res_id: int) -> str | None:
    """The value of a string resource in resources.arsc (first configuration that defines it)."""
    pkg_id, type_id, entry = res_id >> 24, (res_id >> 16) & 0xFF, res_id & 0xFFFF
    ctype, header, _size = struct.unpack_from("<HHI", arsc, 0)
    if ctype != _TABLE:
        raise AxmlError("not a resource table")
    pos, values = header, []
    while pos + 8 <= len(arsc):
        ctype, header, size = struct.unpack_from("<HHI", arsc, pos)
        if size < 8:
            raise AxmlError("corrupt resource table chunk")
        if ctype == _STRING_POOL and not values:
            values = _strings(arsc, pos)
        elif ctype == _PACKAGE and struct.unpack_from("<I", arsc, pos + 8)[0] == pkg_id:
            p = pos + header
            while p + 8 <= pos + size:
                t, th, ts = struct.unpack_from("<HHI", arsc, p)
                if ts < 8:
                    raise AxmlError("corrupt resource table chunk")
                if t == _TYPE and arsc[p + 8] == type_id:
                    value = _type_entry_string(arsc, p, th, entry, values)
                    if value is not None:
                        return value
                p += ts
        pos += size
    return None


def _type_entry_string(arsc: bytes, chunk: int, header: int, entry: int, values: list[str]) -> str | None:
    flags = arsc[chunk + 9]
    count, entries_start = struct.unpack_from("<II", arsc, chunk + 12)
    index = chunk + header
    if flags & _FLAG_SPARSE:  # sorted (u16 entry index, u16 offset/4) pairs
        for i in range(count):
            idx, off4 = struct.unpack_from("<HH", arsc, index + 4 * i)
            if idx == entry:
                return _entry_string(arsc, chunk + entries_start + 4 * off4, values)
        return None
    if entry >= count:
        return None
    if flags & _FLAG_OFFSET16:
        off = struct.unpack_from("<H", arsc, index + 2 * entry)[0]
        if off == _NO_ENTRY16:
            return None
        off *= 4
    else:
        off = struct.unpack_from("<I", arsc, index + 4 * entry)[0]
        if off == _NO_ENTRY:
            return None
    return _entry_string(arsc, chunk + entries_start + off, values)


def _entry_string(arsc: bytes, e: int, values: list[str]) -> str | None:
    size, flags = struct.unpack_from("<HH", arsc, e)
    if flags & _ENTRY_COMPLEX:
        return None
    if flags & _ENTRY_COMPACT:  # Android 14 compact entry: data type in the high byte of flags, data inline
        vtype, data = flags >> 8, struct.unpack_from("<I", arsc, e + 4)[0]
    else:
        _vsize, _res0, vtype, data = struct.unpack_from("<HBBI", arsc, e + size)
    return values[data] if vtype == _TYPE_STRING and data < len(values) else None


def string_locales(arsc: bytes) -> dict[str, int]:
    """How many string resources each locale of resources.arsc defines, by BCP 47 tag: {"": 413, "de": 364,
    "pt-PT": 255, ...} ("" is the default, unqualified configuration; configurations that differ in other
    qualifiers too are added to their locale's count)."""
    try:
        return _string_locales(arsc)
    except (struct.error, IndexError, UnicodeError, ValueError) as e:
        raise AxmlError(f"corrupt resource table ({e})") from None


def _string_locales(arsc: bytes) -> dict[str, int]:
    ctype, header, _size = struct.unpack_from("<HHI", arsc, 0)
    if ctype != _TABLE:
        raise AxmlError("not a resource table")
    counts: dict[str, int] = {}
    pos = header
    while pos + 8 <= len(arsc):
        ctype, header, size = struct.unpack_from("<HHI", arsc, pos)
        if size < 8:
            raise AxmlError("corrupt resource table chunk")
        if ctype == _PACKAGE:
            type_strings = struct.unpack_from("<I", arsc, pos + 268)[0]
            id_offset = struct.unpack_from("<I", arsc, pos + 284)[0] if header >= 288 else 0
            names = _strings(arsc, pos + type_strings)
            if "string" in names:
                string_type = names.index("string") + 1 + id_offset
                p = pos + header
                while p + 8 <= pos + size:
                    t, th, ts = struct.unpack_from("<HHI", arsc, p)
                    if ts < 8:
                        raise AxmlError("corrupt resource table chunk")
                    if t == _TYPE and arsc[p + 8] == string_type:
                        # ResTable_config from p + 20: size, mcc, mnc, then language[2] and country[2]
                        tag = _locale_part(arsc[p + 28:p + 30], ord("a"))
                        region = _locale_part(arsc[p + 30:p + 32], ord("0"))
                        if tag and region:
                            tag += "-" + region
                        counts[tag] = counts.get(tag, 0) + _entry_count(arsc, p, th)
                    p += ts
        pos += size
    return counts


def _locale_part(two: bytes, base: int) -> str:
    """A ResTable_config language or region: two letters, or three packed into two bytes."""
    if not two[0]:
        return ""
    if two[0] & 0x80:
        first = two[1] & 0x1F
        second = ((two[1] & 0xE0) >> 5) | ((two[0] & 0x03) << 3)
        third = (two[0] & 0x7C) >> 2
        return "".join(chr(base + c) for c in (first, second, third))
    return two.decode("ascii")


def _entry_count(arsc: bytes, chunk: int, header: int) -> int:
    flags = arsc[chunk + 9]
    count = struct.unpack_from("<I", arsc, chunk + 12)[0]
    index = chunk + header
    if flags & _FLAG_SPARSE:
        return count
    if flags & _FLAG_OFFSET16:
        return sum(1 for (off,) in struct.iter_unpack("<H", arsc[index:index + 2 * count]) if off != _NO_ENTRY16)
    return sum(1 for (off,) in struct.iter_unpack("<I", arsc[index:index + 4 * count]) if off != _NO_ENTRY)


def app_identity(manifest: bytes, arsc: bytes | None) -> dict[str, object]:
    """Manifest attributes with a versionName reference resolved through resources.arsc."""
    attrs = manifest_attributes(manifest)
    ref = attrs.get("versionName")
    if isinstance(ref, Reference):
        try:
            attrs["versionName"] = resolve_string(arsc, ref) if arsc else None
        except (AxmlError, struct.error, IndexError, UnicodeError):
            attrs["versionName"] = None  # the version is cosmetic here; versionCode is what patches use
    return attrs


def read_apk_manifest(apk: str) -> dict[str, object]:
    try:
        with zipfile.ZipFile(apk) as z:
            try:
                manifest = z.read("AndroidManifest.xml")
            except KeyError:
                raise AxmlError(f"{apk}: no AndroidManifest.xml and no apks inside -- neither an apk nor a "
                                "split bundle") from None
            arsc = z.read("resources.arsc") if "resources.arsc" in z.namelist() else None
    except zipfile.BadZipFile:
        raise AxmlError(f"{apk}: not an apk (not a zip file)") from None
    return app_identity(manifest, arsc)


def read_decoded_manifest(root: str) -> dict[str, object] | None:
    """The same for an `apktool d -r` tree (binary manifest and resources.arsc kept as they were)."""
    try:
        with open(os.path.join(root, "AndroidManifest.xml"), "rb") as f:
            manifest = f.read()
    except OSError:
        return None
    if manifest[:2] != b"\x03\x00":  # a text manifest: resources were decoded, apktool.yml has the version
        return None
    arsc_path = os.path.join(root, "resources.arsc")
    arsc = open(arsc_path, "rb").read() if os.path.isfile(arsc_path) else None
    return app_identity(manifest, arsc)


def decoded_identity(root: str) -> dict[str, object]:
    """package / versionCode / versionName of an apktool tree: from the binary manifest when resources
    were not decoded (-r), else from apktool.yml.  {} if neither is readable."""
    ident = read_decoded_manifest(root)
    if ident is not None:
        return ident
    out: dict[str, object] = {}
    try:
        with open(os.path.join(root, "apktool.yml"), encoding="utf-8") as f:
            yml = f.read()
    except OSError:
        return out
    for key in ("versionCode", "versionName"):
        m = re.search(r"^\s*" + key + r":\s*'?([^'\n]+)", yml, re.M)
        if m:
            value = m.group(1).strip()
            out[key] = int(value) if key == "versionCode" and value.isdigit() else value
    return out


# -- editing ----------------------------------------------------------------------------------------
# A binary XML file is a header, a string pool, a resource map -- the resource id of each attribute
# name, for the first strings of the pool -- and one chunk per namespace, element start, element end
# and text node.  Every name and string value is an index into the pool.  Android looks attributes
# of the android: namespace up by the id the resource map gives their name, not by the name.

_XML, _START_NAMESPACE, _END_NAMESPACE, _END_ELEMENT, _CDATA = 0x0003, 0x0100, 0x0101, 0x0103, 0x0104
_TYPE_INT_BOOLEAN = 0x12
ANDROID_NS = "http://schemas.android.com/apk/res/android"
NAME, REQUIRED, TARGET_SDK_VERSION = 0x01010003, 0x0101028E, 0x01010270  # android:name / required / targetSdkVersion


class Attribute:
    __slots__ = ("ns", "name", "raw", "type", "data")

    def __init__(self, ns: int, name: int, raw: int, vtype: int, data: int):
        self.ns, self.name, self.raw, self.type, self.data = ns, name, raw, vtype, data


class Node:
    """One chunk after the resource map.  a / b: a namespace's prefix / uri, an element's namespace /
    name, a text node's text / (unused); attrs and ids (id, class, style attribute indices) for an
    element start; value (type, data) for a text node."""
    __slots__ = ("type", "line", "comment", "a", "b", "attrs", "ids", "value")

    def __init__(self, ctype: int, line: int, comment: int, a: int, b: int, attrs: list[Attribute] | None = None,
                 ids: tuple[int, int, int] = (0, 0, 0), value: tuple[int, int] = (0, 0)):
        self.type, self.line, self.comment, self.a, self.b = ctype, line, comment, a, b
        self.attrs, self.ids, self.value = attrs or [], ids, value


class Document:
    """A binary XML file, editable: parse, change strings and nodes, serialize with to_bytes()."""

    def __init__(self, buf: bytes):
        try:
            self._parse(buf)
        except (struct.error, IndexError, UnicodeError) as e:
            raise AxmlError(f"corrupt binary XML ({e})") from None

    def _parse(self, buf: bytes) -> None:
        if len(buf) < 8 or struct.unpack_from("<HH", buf, 0) != (_XML, 8):
            raise AxmlError("not a binary XML file")
        pos, end = 8, min(len(buf), struct.unpack_from("<I", buf, 4)[0])
        self.strings: list[str] = []
        self.utf8 = False
        self.resmap: list[int] = []
        self.nodes: list[Node] = []
        while pos + 8 <= end:
            ctype, header, size = struct.unpack_from("<HHI", buf, pos)
            if size < 8 or pos + size > end:
                raise AxmlError("corrupt chunk")
            if ctype == _STRING_POOL:
                if struct.unpack_from("<I", buf, pos + 12)[0]:
                    raise AxmlError("styled strings in a binary XML file")
                self.strings = _strings(buf, pos)
                self.utf8 = bool(struct.unpack_from("<I", buf, pos + 16)[0] & _UTF8)
            elif ctype == _RESOURCE_MAP:
                self.resmap = list(struct.unpack_from(f"<{(size - header) // 4}I", buf, pos + header))
            elif ctype in (_START_NAMESPACE, _END_NAMESPACE, _END_ELEMENT, _START_ELEMENT, _CDATA):
                if header != 16:
                    raise AxmlError(f"unexpected node header size {header}")
                line, comment, a, b = struct.unpack_from("<IIII", buf, pos + 8)
                node = Node(ctype, line, comment, a, b)
                if ctype == _START_ELEMENT:
                    attr_start, attr_size, count, *ids = struct.unpack_from("<HHHHHH", buf, pos + 24)
                    if attr_start != 20 or attr_size != 20 or size != 36 + 20 * count:
                        raise AxmlError("unexpected element layout")
                    for i in range(count):
                        ans, aname, raw, vsize, _res0, vtype, data = struct.unpack_from("<IIIHBBI", buf, pos + 36 + 20 * i)
                        if vsize != 8:
                            raise AxmlError("unexpected attribute value size")
                        node.attrs.append(Attribute(ans, aname, raw, vtype, data))
                    node.ids = tuple(ids)
                elif ctype == _CDATA:
                    node.value = struct.unpack_from("<3xBI", buf, pos + 20)  # the text's typed value: type, data
                self.nodes.append(node)
            else:
                raise AxmlError(f"unexpected chunk type {ctype:#06x}")
            pos += size

    # -- strings ---------------------------------------------------------------------------------
    def string(self, s: str) -> int:
        """Index of s in the pool, added at the end if absent."""
        if s in self.strings:
            return self.strings.index(s)
        self.strings.append(s)
        return len(self.strings) - 1

    def attribute_name(self, name: str, res_id: int) -> int:
        """Index of an attribute name with its resource id: in the resource-mapped part of the pool,
        added at its end -- moving every later string up by one -- if absent."""
        for i, rid in enumerate(self.resmap):
            if rid == res_id and self.strings[i] == name:
                return i
        at = len(self.resmap)
        self.strings.insert(at, name)
        self.resmap.append(res_id)
        for node in self.nodes:
            for attr in node.attrs:
                attr.ns, attr.name, attr.raw = (_moved(attr.ns, at), _moved(attr.name, at), _moved(attr.raw, at))
                if attr.type == _TYPE_STRING:
                    attr.data = _moved(attr.data, at)
            node.comment, node.a = _moved(node.comment, at), _moved(node.a, at)
            if node.type != _CDATA:
                node.b = _moved(node.b, at)
            elif node.value[0] == _TYPE_STRING:
                node.value = (node.value[0], _moved(node.value[1], at))
        return at

    # -- reading ---------------------------------------------------------------------------------
    def elements(self, name: str) -> list[int]:
        """Indices in nodes of the element starts named name (no namespace)."""
        return [i for i, n in enumerate(self.nodes)
                if n.type == _START_ELEMENT and n.a == _NO_STRING and self.strings[n.b] == name]

    def attribute(self, node: Node, res_id: int) -> Attribute | None:
        """An element's attribute by the resource id of its name."""
        for attr in node.attrs:
            if attr.name < len(self.resmap) and self.resmap[attr.name] == res_id:
                return attr
        return None

    def namespace(self, uri: str) -> int:
        """Pool index of a namespace uri the document declares."""
        for n in self.nodes:
            if n.type == _START_NAMESPACE and n.b != _NO_STRING and self.strings[n.b] == uri:
                return n.b
        raise AxmlError(f"no xmlns for {uri}")

    # -- writing ---------------------------------------------------------------------------------
    def to_bytes(self) -> bytes:
        body = self._pool() + self._resmap() + b"".join(self._node(n) for n in self.nodes)
        return struct.pack("<HHI", _XML, 8, 8 + len(body)) + body

    def _pool(self) -> bytes:
        data, offsets = bytearray(), []
        for s in self.strings:
            offsets.append(len(data))
            if self.utf8:
                b = s.encode("utf-8")
                data += _len8(len(s.encode("utf-16-le")) // 2) + _len8(len(b)) + b + b"\0"
            else:
                b = s.encode("utf-16-le")
                n = len(b) // 2
                data += (struct.pack("<HH", 0x8000 | n >> 16, n & 0xFFFF) if n > 0x7FFF else struct.pack("<H", n)) + b + b"\0\0"
        data += bytes(-len(data) % 4)
        start = 28 + 4 * len(self.strings)
        head = struct.pack("<HHIIIIII", _STRING_POOL, 28, start + len(data), len(self.strings), 0,
                           _UTF8 if self.utf8 else 0, start, 0)
        return head + struct.pack(f"<{len(offsets)}I", *offsets) + bytes(data)

    def _resmap(self) -> bytes:
        if not self.resmap:
            return b""
        return struct.pack("<HHI", _RESOURCE_MAP, 8, 8 + 4 * len(self.resmap)) + struct.pack(f"<{len(self.resmap)}I", *self.resmap)

    @staticmethod
    def _node(n: Node) -> bytes:
        ext = struct.pack("<II", n.a, n.b)
        if n.type == _START_ELEMENT:
            ext += struct.pack("<HHHHHH", 20, 20, len(n.attrs), *n.ids)
            ext += b"".join(struct.pack("<IIIHBBI", a.ns, a.name, a.raw, 8, 0, a.type, a.data) for a in n.attrs)
        elif n.type == _CDATA:
            ext = struct.pack("<I", n.a) + struct.pack("<HBBI", 8, 0, *n.value)
        return struct.pack("<HHIII", n.type, 16, 16 + len(ext), n.line, n.comment) + ext


def _moved(index: int, at: int) -> int:
    return index + 1 if index != _NO_STRING and index >= at else index


def _len8(n: int) -> bytes:
    return bytes([0x80 | n >> 8, n & 0xFF]) if n > 0x7F else bytes([n])


def target_sdk(buf: bytes) -> int | None:
    """<uses-sdk android:targetSdkVersion> of a binary manifest (None if it has none)."""
    doc = Document(buf)
    for i in doc.elements("uses-sdk"):
        attr = doc.attribute(doc.nodes[i], TARGET_SDK_VERSION)
        if attr and attr.type in (_TYPE_INT_DEC, _TYPE_INT_HEX):
            return attr.data
    return None


def uses_libraries(buf: bytes) -> list[tuple[str, str | None]]:
    """(android:name, comment) of every <uses-library> of a binary manifest."""
    doc = Document(buf)
    out = []
    for i in doc.elements("uses-library"):
        node = doc.nodes[i]
        attr = doc.attribute(node, NAME)
        if attr and attr.raw != _NO_STRING:
            out.append((doc.strings[attr.raw], None if node.comment == _NO_STRING else doc.strings[node.comment]))
    return out


def add_uses_library(buf: bytes, library: str, required: bool, comment: str | None = None) -> bytes:
    """A binary manifest with <uses-library android:name=library android:required=...> as the first
    child of <application>.  comment goes in the element's comment field, which aapt leaves empty and
    Android ignores."""
    doc = Document(buf)
    apps = doc.elements("application")
    if len(apps) != 1:
        raise AxmlError(f"expected one <application>, found {len(apps)}")
    name, req = doc.attribute_name("name", NAME), doc.attribute_name("required", REQUIRED)  # may move strings
    ns, tag, value = doc.namespace(ANDROID_NS), doc.string("uses-library"), doc.string(library)
    note = _NO_STRING if comment is None else doc.string(comment)
    at, line = apps[0] + 1, doc.nodes[apps[0]].line
    attrs = [Attribute(ns, name, value, _TYPE_STRING, value),  # sorted by resource id, as Android expects
             Attribute(ns, req, _NO_STRING, _TYPE_INT_BOOLEAN, 0xFFFFFFFF if required else 0)]
    doc.nodes[at:at] = [Node(_START_ELEMENT, line, note, _NO_STRING, tag, attrs),
                        Node(_END_ELEMENT, line, _NO_STRING, _NO_STRING, tag)]
    return doc.to_bytes()
