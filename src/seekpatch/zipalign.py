"""zipalign in Python: stored (uncompressed) entries start at a 4-byte boundary, native libraries at
a 16 KiB page boundary (Android 15+ devices may use 16 KiB pages; 16 KiB is also 4 KiB aligned).

Apps with extractNativeLibs="false" (the Seek app) map their .so files straight out of the apk, so
those must be stored and page aligned.  Padding goes into an extra field with the same 0xD935 id
the Android zipalign tool uses.
"""
from __future__ import annotations

import struct
import zipfile

ALIGN = 4
SO_ALIGN = 16384
_EXTRA_ID = 0xD935
_LOCAL_HEADER = 30


def _encoded_name(name: str) -> bytes:
    try:
        return name.encode("ascii")
    except UnicodeEncodeError:
        return name.encode("utf-8")


def alignment_for(name: str) -> int:
    return SO_ALIGN if name.endswith(".so") else ALIGN


def stale_signing_file(name: str) -> bool:
    """META-INF leftovers of the original build: its signature, and build metadata that the new
    signature would not cover.  META-INF/services/ and other resources stay."""
    if name.startswith("META-INF/com/android/build/"):  # AGP's app-metadata.properties
        return True
    if not name.startswith("META-INF/") or "/" in name[len("META-INF/"):]:
        return False
    base = name[len("META-INF/"):]
    return base in ("MANIFEST.MF", "version-control-info.textproto") or base.endswith((".SF", ".RSA", ".DSA", ".EC"))


def zipalign(src: str, dst: str, drop=stale_signing_file) -> None:
    with zipfile.ZipFile(src) as zin, open(dst, "wb") as raw, zipfile.ZipFile(raw, "w") as zout:
        for info in zin.infolist():
            if drop and drop(info.filename):
                continue
            data = zin.read(info)
            out = zipfile.ZipInfo(info.filename, date_time=max(info.date_time, (1980, 1, 1, 0, 0, 0)))
            out.compress_type = info.compress_type
            out.external_attr = info.external_attr
            out.create_system = info.create_system
            if info.compress_type == zipfile.ZIP_STORED:
                align = alignment_for(info.filename)
                data_start = raw.tell() + _LOCAL_HEADER + len(_encoded_name(info.filename))
                length = (-data_start) % align
                while length < 6:  # room for the extra field header (id, size, alignment)
                    length += align
                out.extra = struct.pack("<HHH", _EXTRA_ID, length - 4, align) + b"\0" * (length - 6)
            zout.writestr(out, data)


def check(path: str) -> list[str]:
    """Stored entries that are not aligned (empty list = aligned)."""
    bad = []
    with zipfile.ZipFile(path) as z, open(path, "rb") as f:
        for info in z.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                continue
            f.seek(info.header_offset)
            header = f.read(_LOCAL_HEADER)
            name_len, extra_len = struct.unpack("<HH", header[26:30])
            data_start = info.header_offset + _LOCAL_HEADER + name_len + extra_len
            if data_start % alignment_for(info.filename):
                bad.append(f"{info.filename} @ {data_start}")
    return bad
