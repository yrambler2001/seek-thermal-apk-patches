"""zipalign, the binary manifest / resource table reader, and the --side-by-side manifest rename."""
from __future__ import annotations

import struct
import zipfile

import pytest
from conftest import FIXTURES

from seekpatch import apk, axml, manifest, zipalign
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
