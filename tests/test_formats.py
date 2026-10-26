"""zipalign, the binary manifest / resource table reader, the --side-by-side manifest rename, and
reading split bundles."""
from __future__ import annotations

import struct
import zipfile

import pytest
from conftest import FIXTURES, split_apk, zip_bytes

from seekpatch import apk, axml, bundle, manifest, zipalign
from seekpatch.smali import SmaliTree

# zipalign ---------------------------------------------------------------------------------------


def _data_offset(path, name):
    with zipfile.ZipFile(path) as z, open(path, "rb") as f:
        info = z.getinfo(name)
        f.seek(info.header_offset)
        h = f.read(30)
        n, e = struct.unpack("<HH", h[26:30])
        return info.header_offset + 30 + n + e


def test_zipalign_aligns_stored_entries_and_keeps_content(tmp_path):
    src, dst = tmp_path / "in.apk", tmp_path / "out.apk"
    files = {
        "AndroidManifest.xml": (b"x" * 33, zipfile.ZIP_DEFLATED),
        "resources.arsc": (b"r" * 101, zipfile.ZIP_STORED),
        "lib/arm64-v8a/libfoo.so": (b"\x7fELF" + b"s" * 5000, zipfile.ZIP_STORED),
        "assets/a.png": (b"p" * 7, zipfile.ZIP_STORED),
        "META-INF/CERT.RSA": (b"old signature", zipfile.ZIP_DEFLATED),
        "META-INF/MANIFEST.MF": (b"Manifest-Version: 1.0\n", zipfile.ZIP_DEFLATED),
        "META-INF/services/x.Y": (b"impl", zipfile.ZIP_DEFLATED),
    }
    with zipfile.ZipFile(src, "w") as z:
        for name, (data, method) in files.items():
            z.writestr(zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0)), data, compress_type=method)
    assert zipalign.check(str(src))  # unaligned to begin with
    zipalign.zipalign(str(src), str(dst))
    assert zipalign.check(str(dst)) == []
    assert _data_offset(dst, "lib/arm64-v8a/libfoo.so") % 16384 == 0
    assert _data_offset(dst, "resources.arsc") % 4 == 0
    with zipfile.ZipFile(dst) as z:
        assert set(z.namelist()) == set(files) - {"META-INF/CERT.RSA", "META-INF/MANIFEST.MF"}
        for name in z.namelist():
            assert z.read(name) == files[name][0]
            assert z.getinfo(name).compress_type == files[name][1]


@pytest.mark.parametrize("name, stale", [
    ("META-INF/MANIFEST.MF", True), ("META-INF/CERT.SF", True), ("META-INF/KEY.EC", True),
    ("META-INF/version-control-info.textproto", True), ("META-INF/com/android/build/gradle/app-metadata.properties", True),
    ("META-INF/services/kotlinx.coroutines.internal.MainDispatcherFactory", False),
    ("META-INF/androidx.core_core.version", False), ("META-INF/kotlin/x.SF", False), ("classes.dex", False),
])
def test_stale_signing_files(name, stale):
    assert zipalign.stale_signing_file(name) is stale


# axml -------------------------------------------------------------------------------------------


def test_reads_the_fixture_manifest_with_a_versionname_resource():
    ident = axml.read_decoded_manifest(str(FIXTURES / "project"))
    assert ident["package"] == "org.example.seekfixture"
    assert ident["versionCode"] == 294
    assert ident["versionName"] == "2.3.4"  # @string/version_name, resolved via resources.arsc


def test_rejects_non_binary_xml():
    with pytest.raises(axml.AxmlError):
        axml.manifest_attributes(b"<manifest/>")


@pytest.mark.parametrize("path", ["project/AndroidManifest.xml", "split/AndroidManifest.xml"])
def test_binary_xml_round_trips(path):
    buf = (FIXTURES / path).read_bytes()
    assert axml.Document(buf).to_bytes() == buf


def test_document_rejects_text_xml():
    with pytest.raises(axml.AxmlError, match="not a binary XML"):
        axml.Document(b"<manifest/>")


def test_adds_a_uses_library_to_a_binary_manifest():
    buf = (FIXTURES / "project" / "AndroidManifest.xml").read_bytes()
    before = axml.Document(buf)
    assert axml.REQUIRED not in before.resmap  # the fixture has no android:required: the name is mapped in
    assert axml.uses_libraries(buf) == [] and axml.target_sdk(buf) == 35
    out = axml.add_uses_library(buf, "org.apache.http.legacy", False, "seek-thermal-apk-patches test")
    assert axml.uses_libraries(out) == [("org.apache.http.legacy", "seek-thermal-apk-patches test")]
    assert axml.manifest_attributes(out) == axml.manifest_attributes(buf)  # the strings it moved still resolve
    assert axml.target_sdk(out) == 35
    doc = axml.Document(out)
    assert doc.resmap == before.resmap + [axml.REQUIRED] and doc.strings[len(before.resmap)] == "required"
    starts = [doc.strings[n.b] for n in doc.nodes if n.type == 0x0102]
    assert starts == ["manifest", "uses-sdk", "application", "uses-library", "activity", "intent-filter", "action", "category"]
    lib = doc.nodes[doc.elements("uses-library")[0]]
    assert [(doc.resmap[a.name], a.type, a.data) for a in lib.attrs] == [  # sorted by resource id, as aapt2 writes it
        (axml.NAME, 0x03, doc.strings.index("org.apache.http.legacy")), (axml.REQUIRED, 0x12, 0)]
    assert all(doc.strings[a.ns] == axml.ANDROID_NS for a in lib.attrs)
    assert doc.nodes[doc.elements("uses-library")[0] + 1].type == 0x0103  # and its end
    again = axml.add_uses_library(out, "other.library", True)  # "required" is mapped now: nothing moves
    assert len(axml.Document(again).resmap) == len(doc.resmap)
    assert axml.uses_libraries(again) == [("other.library", None), ("org.apache.http.legacy", "seek-thermal-apk-patches test")]


# manifest (--side-by-side) ----------------------------------------------------------------------

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.app">
    <permission android:name="com.example.app.permission.C2D_MESSAGE" android:protectionLevel="signature"/>
    <uses-permission android:name="com.example.app.permission.C2D_MESSAGE"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <application android:label="@string/app_name" android:name=".App">
        <activity android:name=".Splash" android:label="@string/app_name">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <activity-alias android:name=".Alias" android:targetActivity=".Splash"/>
        <activity android:name="com.example.app.Main"/>
        <provider android:name="androidx.core.content.FileProvider"
            android:authorities="com.example.app.fileprovider;other.authority"/>
    </application>
</manifest>
"""


def test_side_by_side_rename():
    xml, notes = manifest.rename(MANIFEST, "com.example.app.patched", 'Seek "patched" & co')
    assert 'package="com.example.app.patched"' in xml
    assert 'android:name="com.example.app.App"' in xml and 'android:name="com.example.app.Splash"' in xml
    assert 'android:name="com.example.app.Alias"' in xml
    assert 'android:name="com.example.app.Main"' in xml  # classes are not renamed
    assert 'android:authorities="com.example.app.patched.fileprovider;other.authority"' in xml
    assert xml.count("com.example.app.patched.permission.C2D_MESSAGE") == 2
    assert 'android:name="android.permission.CAMERA"' in xml
    assert xml.count('android:label="Seek &quot;patched&quot; &amp; co"') == 2
    assert notes[0] == "package com.example.app -> com.example.app.patched"


def test_side_by_side_needs_a_new_name():
    with pytest.raises(manifest.ManifestError):
        manifest.rename(MANIFEST, "com.example.app", None)


def test_adds_a_uses_library_to_a_text_manifest():
    assert manifest.uses_libraries(MANIFEST) == []
    xml = manifest.add_uses_library(MANIFEST, "org.apache.http.legacy", False, "seek-thermal-apk-patches test")
    assert ('    <application android:label="@string/app_name" android:name=".App">\n'
            "        <!-- seek-thermal-apk-patches test -->\n"
            '        <uses-library android:name="org.apache.http.legacy" android:required="false"/>\n'
            '        <activity android:name=".Splash"') in xml
    assert manifest.uses_libraries(xml) == ["org.apache.http.legacy"]
    with pytest.raises(manifest.ManifestError):
        manifest.add_uses_library('<manifest><application android:label="x"/></manifest>', "a.b", False)


# split installs ---------------------------------------------------------------------------------


@pytest.mark.parametrize("libs, missing", [(["lib/arm64-v8a/libseekip.so"], []), ([], ["libseekip.so"])])
def test_missing_native_libraries(make_project, tmp_path, libs, missing):
    tree = SmaliTree(str(make_project("lambda")))
    path = tmp_path / "app.apk"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("classes.dex", b"")
        for name in libs:
            z.writestr(name, b"\x7fELF")
    assert apk.missing_native_libraries(str(path), tree) == missing


# split bundles ----------------------------------------------------------------------------------

BASE = zip_bytes({"AndroidManifest.xml": (FIXTURES / "project" / "AndroidManifest.xml").read_bytes(),
                  "resources.arsc": (FIXTURES / "project" / "resources.arsc").read_bytes(), "classes.dex": b""})
SPLIT = split_apk()
LAYOUTS = {  # base entry, split entry and the rest, as each format names them
    "xapk": ("org.example.seekfixture.apk", "config.arm64_v8a.apk", {"manifest.json": b"{}", "icon.png": b""}),
    "apkm": ("base.apk", "split_config.arm64_v8a.apk", {"info.json": b"{}"}),
    "apks": ("splits/base-master.apk", "splits/base-arm64_v8a.apk",
             {"toc.pb": b"", "standalones/standalone-arm64_v8a.apk": BASE}),  # a complete apk, not merged
}


def _write(path, entries):
    path.write_bytes(zip_bytes(entries))
    return str(path)


@pytest.mark.parametrize("kind", LAYOUTS)
def test_bundle_base_and_splits(tmp_path, kind):
    base, split, rest = LAYOUTS[kind]
    path = _write(tmp_path / f"app.{kind}", {split: SPLIT, **rest, base: BASE})  # the manifests tell, not the order
    assert bundle.is_bundle(path)
    b = bundle.inspect(path)
    assert b.base == base and b.splits == {split: "config.arm64_v8a"}
    info = apk.app_info(path)
    assert (info.package, info.version_name, info.version_code) == ("org.example.seekfixture", "2.3.4", 294)


def test_an_apk_is_not_a_bundle(tmp_path):
    assert not bundle.is_bundle(_write(tmp_path / "app.apk", {"AndroidManifest.xml": b"", "classes.dex": b""}))
    assert not bundle.is_bundle(_write(tmp_path / "notes.zip", {"readme.txt": b""}))
    (tmp_path / "text.xapk").write_text("not a zip")
    assert not bundle.is_bundle(str(tmp_path / "text.xapk"))


def _encrypted(entries):
    data = bytearray(zip_bytes(entries))
    data[data.find(b"PK\x01\x02") + 8] |= 1  # the central directory's "encrypted" flag
    return bytes(data)


def _other_release(split: bytes) -> bytes:
    """The split with versionCode 295: its Res_value (size 8, type int, data 294) rewritten."""
    m = (FIXTURES / "split" / "AndroidManifest.xml").read_bytes()
    value = struct.pack("<HBBI", 8, 0, 0x10, 294)
    assert m.count(value) == 1
    return split_apk(manifest=m.replace(value, struct.pack("<HBBI", 8, 0, 0x10, 295)))


@pytest.mark.parametrize("entries, match", [
    ({"config.arm64_v8a.apk": SPLIT}, "no base apk"),
    ({"a.apk": BASE, "b.apk": BASE}, "more than one base apk"),
    ({"base.apk": BASE, "config.arm64_v8a.apk": b"not a zip"}, "not an apk"),
    ({"base.apk": BASE, "config.arm64_v8a.apk": _other_release(SPLIT)}, "splits of different releases"),
])
def test_bundle_refusals(tmp_path, entries, match):
    with pytest.raises(bundle.BundleError, match=match):
        bundle.inspect(_write(tmp_path / "app.xapk", entries))


def test_encrypted_bundle(tmp_path):
    (tmp_path / "app.apkm").write_bytes(_encrypted({"base.apk": BASE}))
    with pytest.raises(bundle.BundleError, match="encrypted"):
        bundle.inspect(str(tmp_path / "app.apkm"))
