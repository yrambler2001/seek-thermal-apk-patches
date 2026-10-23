"""Just enough of Android's binary resource formats to read an apk's identity -- the <manifest>
element of the binary AndroidManifest.xml (package, versionCode, versionName) and, when versionName
is a string resource, its value from resources.arsc -- without decoding the whole app."""
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
