"""Split bundles: the .xapk / .apks / .apkm files app stores hand out instead of one apk -- a zip of
the base apk and its config splits (native code per ABI, resources per screen density and language).

APKEditor merges them into one apk and drops the manifest attributes that make Android insist on
the splits; the merged apk is then patched like any other.  The file name does not matter: any zip
of apks without a manifest of its own is a bundle, so the files `adb pull` gives for a split install,
zipped together, work too.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Callable

from . import axml
from .toolchain import Toolchain

_ENCRYPTED = 0x1  # zip general-purpose flag bit 0


class BundleError(Exception):
    """A bundle that cannot be merged."""


@dataclass
class Bundle:
    base: str                    # the base apk's entry in the bundle
    splits: dict[str, str]       # entry -> split name ("config.arm64_v8a")
    identity: dict[str, object]  # the base apk's manifest attributes


def is_bundle(path: str) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    return "AndroidManifest.xml" not in names and bool(_members(names))


def _members(names: list[str]) -> list[str]:
    """The apks to merge.  bundletool's .apks keeps them in splits/ (its standalones/ are complete
    apks for old Android versions); the other formats keep them at the top level."""
    apks = [n for n in names if n.lower().endswith(".apk")]
    in_splits = [n for n in apks if n.startswith("splits/") and n.count("/") == 1]
    return in_splits or [n for n in apks if "/" not in n]


def _manifest(apk: zipfile.ZipFile, entry: str) -> dict[str, object]:
    try:
        manifest = apk.read("AndroidManifest.xml")
    except KeyError:
        raise BundleError(f"{entry} in the bundle has no AndroidManifest.xml") from None
    arsc = apk.read("resources.arsc") if "resources.arsc" in apk.namelist() else None
    try:
        return axml.app_identity(manifest, arsc)
    except axml.AxmlError as e:
        raise BundleError(f"{entry} in the bundle: {e}") from None


def inspect(path: str) -> Bundle:
    """Which entry is the base and which are splits, by their manifests; refuses bundles that are not
    one app at one version."""
    name = os.path.basename(path)
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise BundleError(f"{name}: not a zip file") from None
    with z:
        members = _members(z.namelist())
        if not members:
            raise BundleError(f"{name}: no apks inside")
        if any(z.getinfo(m).flag_bits & _ENCRYPTED for m in members):
            raise BundleError(f"{name} is encrypted (as APKMirror's newer .apkm files are); get the .apk, "
                              "or a bundle that is a plain zip")
        bases, splits, idents = [], {}, {}
        for m in members:
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(m))) as inner:
                    ident = _manifest(inner, m)
            except zipfile.BadZipFile:
                raise BundleError(f"{m} in the bundle is not an apk") from None
            idents[m] = ident
            if ident.get("split"):
                splits[m] = str(ident["split"])
            else:
                bases.append(m)
    if len(bases) != 1:
        raise BundleError(f"{name}: {'no base apk' if not bases else 'more than one base apk: ' + ', '.join(bases)} "
                          "-- not a split bundle of one app")
    base = idents[bases[0]]
    for m, ident in idents.items():
        if ident.get("package") != base.get("package"):
            raise BundleError(f"{name}: {m} belongs to {ident.get('package')}, the base to {base.get('package')}")
        if "versionCode" in ident and ident["versionCode"] != base.get("versionCode"):
            raise BundleError(f"{name}: {m} is versionCode {ident['versionCode']}, the base "
                              f"{base.get('versionCode')} -- splits of different releases")
    return Bundle(bases[0], splits, base)


def base_identity(path: str) -> dict[str, object]:
    """The base apk's manifest attributes (package, versionCode, versionName)."""
    return inspect(path).identity


def merge(tc: Toolchain, path: str, out: str, log: Callable[[str], None] = print) -> None:
    """Merge the bundle into one unsigned apk at `out`."""
    b = inspect(path)
    with tempfile.TemporaryDirectory(prefix="seek-patch-merge-") as tmp, zipfile.ZipFile(path) as z:
        if not b.splits:
            log(f"bundle {os.path.basename(path)}: a base apk without splits")
            with z.open(b.base) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return
        names = sorted(s[len("config."):] if s.startswith("config.") else s for s in b.splits.values())
        log(f"merge  {os.path.basename(path)}: base + {len(names)} split{'' if len(names) == 1 else 's'} "
            f"({', '.join(names)}), with APKEditor")
        folder = os.path.join(tmp, "splits")
        os.mkdir(folder)
        for i, m in enumerate([b.base, *b.splits]):
            safe = re.sub(r"[^\w.-]", "_", os.path.basename(m))  # only the apks go in; the index keeps names unique
            with z.open(m) as src, open(os.path.join(folder, f"{i:02d}-{safe}"), "wb") as dst:
                shutil.copyfileobj(src, dst)
        tc.run_jar(tc.merger(log), ["m", "-i", folder, "-o", out, "-f", "-clean-meta"], "APKEditor merge")
