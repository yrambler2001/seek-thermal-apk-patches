"""http_legacy: the app gets Android's Apache HTTP library, which it uses without declaring it.

Android 9 took Apache HTTP (org.apache.http.*) off an app's class path.  It still ships with the
system, as the shared library org.apache.http.legacy, and is added for an app that targets API 27
or lower, or that declares it in its manifest:

    <uses-library android:name="org.apache.http.legacy" android:required="false"/>

2.1.6 - 2.3.1 target API 28 - 34, use it and do not declare it, so on Android 9 and later each use
throws NoClassDefFoundError: Google Analytics' fallback store about 15 s after launch (which kills
the app, see no_analytics), and in 2.1.6 - 2.2.3 the account pages, the downloads from Seek's server
and 2.2.3's JSON client.  Seek added this line in 2.3.3.

The patch adds the same line, as the first child of <application>: to the binary manifest (apktool
d -r, the default; seekpatch.axml) or to the text one when resources are decoded (--side-by-side).
required="false" lets the app install on a device without the library, as Google recommends; every
Android 9+ phone has it.  It refuses an app that targets API 27 or lower (Android adds the library
by itself), one that already declares it, and one whose code does not use Apache HTTP.
"""
from __future__ import annotations

import os
import re

from .. import axml, manifest
from ..smali import MANIFEST, AlreadyApplied, PatchError, SmaliTree
from .base import Options, mark

NAME = "http_legacy"
SUMMARY = "declare Android's Apache HTTP library: 2.1.6 - 2.3.1 use it undeclared and crash with it on Android 9+"
VERSIONS = "2.1.6 - 2.3.1"
RECOMMENDED = True

NOTE = mark(NAME).lstrip("# ")  # "seek-patch http_legacy": the comment on the added element
LIBRARY = "org.apache.http.legacy"
DECLARED_FROM = 28  # Android 9: from this targetSdkVersion on, the library has to be declared
USE = "Lorg/apache/http/"


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    data = tree.manifest
    try:
        if data[:2] == b"\x03\x00":  # binary
            declared = axml.uses_libraries(data)
            if any(comment == NOTE for _, comment in declared):
                raise AlreadyApplied(f"{NAME}: already applied")
            libraries, target = [n for n, _ in declared], axml.target_sdk(data)
        else:
            xml = data.decode("utf-8")
            if NOTE in xml:
                raise AlreadyApplied(f"{NAME}: already applied")
            libraries, target = manifest.uses_libraries(xml), _yml_target(tree.root)
    except (axml.AxmlError, UnicodeError) as e:
        raise PatchError(f"{NAME}: cannot read {MANIFEST}: {e}") from None
    if LIBRARY in libraries:
        raise PatchError(f"{NAME}: the app already declares {LIBRARY}")
    if target is None:
        raise PatchError(f"{NAME}: no targetSdkVersion in {MANIFEST}")
    if target < DECLARED_FROM:
        raise PatchError(f"{NAME}: the app targets API {target}: Android adds {LIBRARY} by itself below {DECLARED_FROM}")
    users = tree.containing(USE)
    if not users:
        raise PatchError(f"{NAME}: the app's code does not use Apache HTTP")
    try:
        if data[:2] == b"\x03\x00":
            tree.set_manifest(axml.add_uses_library(data, LIBRARY, False, NOTE))
        else:
            tree.set_manifest(manifest.add_uses_library(data.decode("utf-8"), LIBRARY, False, NOTE).encode("utf-8"))
    except (axml.AxmlError, manifest.ManifestError) as e:
        raise PatchError(f"{NAME}: {e}") from None
    return [f'{MANIFEST}: <uses-library android:name="{LIBRARY}" android:required="false"/> '
            f"(targetSdkVersion {target}; Apache HTTP used in {len(users)} classes)"]


def _yml_target(root: str) -> int | None:
    """targetSdkVersion from apktool.yml, where apktool puts it when it decodes the manifest."""
    try:
        with open(os.path.join(root, "apktool.yml"), encoding="utf-8") as f:
            m = re.search(r"^\s*targetSdkVersion:\s*'?(\d+)", f.read(), re.M)
    except OSError:
        return None
    return int(m.group(1)) if m else None
