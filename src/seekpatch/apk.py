"""(merge) -> decode -> patch -> build -> align -> sign.

A split bundle (.xapk / .apks / .apkm) is merged into one apk first (seekpatch/bundle.py).  The default mode decodes smali only (apktool -r): resources.arsc and the binary manifest are carried
over byte for byte, so a rebuild cannot break resources and the app keeps its package name -- it
replaces the store app.  --side-by-side decodes resources too, to rename the package.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Callable

from . import axml, bundle, manifest, zipalign
from .patches import BY_NAME, Options
from .smali import AlreadyApplied, PatchError, SmaliTree
from .toolchain import KEY_ALIAS, KEY_PASSWORD, Toolchain, ToolchainError

SEEK_PACKAGE = "com.tyriansystems.SeekThermal"


@dataclass
class AppInfo:
    package: str
    version_name: str | None  # None when the manifest only references a string resource
    version_code: int | str

    def __str__(self) -> str:
        return f"{self.package} {self.version_name or ''} (versionCode {self.version_code})".replace("  ", " ")


def app_info(apk: str) -> AppInfo:
    """The app's identity, of an apk or of a split bundle's base apk."""
    a = bundle.base_identity(apk) if bundle.is_bundle(apk) else axml.read_apk_manifest(apk)
    name = a.get("versionName")
    return AppInfo(str(a.get("package", "?")), str(name) if name else None, a.get("versionCode", "?"))


def decoded_version(root: str) -> str | None:
    name = axml.decoded_identity(root).get("versionName")
    return str(name) if name else None


class ApkError(Exception):
    """The apk cannot be patched as it is (e.g. part of a split install)."""


_LOAD_LIBRARY = "Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V"


def missing_native_libraries(apk: str, tree: SmaliTree) -> list[str]:
    """Libraries the code loads (System.loadLibrary("name")) that the apk does not contain -- the
    sign of a base apk from a split install, whose native code lives in a config split."""
    loaded = set()
    for p in tree.containing(_LOAD_LIBRARY):
        for m in re.finditer(r'const-string ([vp]\d+), "([\w.-]+)"\n(?:[ \t]*(?:\.line \d+)?[ \t]*\n)*'
                             r"[ \t]*invoke-static \{\1\}, " + re.escape(_LOAD_LIBRARY), tree.get(p)):
            loaded.add(m.group(2))
    with zipfile.ZipFile(apk) as z:
        shipped = {os.path.basename(n)[3:-3] for n in z.namelist()
                   if n.startswith("lib/") and os.path.basename(n).startswith("lib") and n.endswith(".so")}
    return sorted(f"lib{name}.so" for name in loaded - shipped)


def single_apk(tc: Toolchain, path: str, tmp: str, log: Callable[[str], None] = print) -> str:
    """The apk itself, or the apk merged from a split bundle (written into tmp)."""
    if not bundle.is_bundle(path):
        return path
    merged = os.path.join(tmp, "merged.apk")
    bundle.merge(tc, path, merged, log)
    return merged


def _missing_hint(path: str) -> str:
    if bundle.is_bundle(path):
        return "the bundle has no split with them"
    return "a base apk of a split install?  Use the whole bundle"


def decode(tc: Toolchain, apk: str, out: str, resources: bool) -> None:
    args = ["d", "-f", "-o", out, apk]
    if not resources:
        args.insert(1, "-r")
    tc.run_jar(tc.apktool, args, "apktool decode")


def build(tc: Toolchain, src: str, out: str) -> None:
    tc.run_jar(tc.apktool, ["b", "-o", out, src], "apktool build")


def sign(tc: Toolchain, unsigned: str, out: str, log: Callable[[str], None] = print) -> str:
    """Align (in Python) and sign with the per-user key; returns the key's path."""
    with tempfile.TemporaryDirectory(prefix="seek-patch-sign-") as tmp:
        aligned = os.path.join(tmp, "aligned.apk")
        zipalign.zipalign(unsigned, aligned)
        ks = tc.keystore(log)
        args = ["-a", aligned, "-o", os.path.join(tmp, "signed"), "--allowResign", "--skipZipAlign",
                "--ks", ks, "--ksAlias", KEY_ALIAS, "--ksPass", KEY_PASSWORD, "--ksKeyPass", KEY_PASSWORD]
        tc.run_jar(tc.signer, args, "uber-apk-signer")
        signed = [f for f in os.listdir(os.path.join(tmp, "signed")) if f.endswith(".apk")]
        if len(signed) != 1:
            raise ToolchainError(f"uber-apk-signer produced {signed}")
        produced = os.path.join(tmp, "signed", signed[0])
        bad = zipalign.check(produced)
        if bad:
            raise ToolchainError(f"signed apk lost its alignment: {bad[:3]}")
        shutil.move(produced, out)
    return ks


@dataclass
class Plan:
    patches: list[str]
    options: Options = field(default_factory=Options)
    side_by_side: bool = False
    package: str | None = None   # side-by-side package name (default: <original>.patched)
    label: str | None = None     # side-by-side launcher label
    skip_unavailable: bool = False  # the default set: skip patches that do not apply to this version


def apply_patches(root: str, plan: Plan, log: Callable[[str], None] = print, tree: SmaliTree | None = None) -> list[str]:
    """Apply the plan's patches to a decoded tree in place, all or nothing per patch.  Returns the
    names applied.  With plan.skip_unavailable a patch that does not apply is reported and skipped
    (it changed nothing); otherwise its PatchError propagates."""
    tree = tree or SmaliTree(root)
    applied = []
    for name in plan.patches:
        patch = BY_NAME[name]
        try:
            with tree.transaction():
                lines = patch.apply(tree, plan.options)
        except PatchError as e:
            if not plan.skip_unavailable or isinstance(e, AlreadyApplied):
                raise
            why = str(e)
            log(f"skip   {name}: {why[len(name) + 2:] if why.startswith(name + ': ') else why}")
            continue
        log(f"patch  {name}")
        for line in lines:
            log(f"       {line}")
        applied.append(name)
    if not applied:
        raise PatchError("none of the patches applies to this apk")
    tree.save()
    return applied


def check(tc: Toolchain, apk: str, log: Callable[[str], None] = print) -> dict[str, str | None]:
    """Dry run of every patch on its own: name -> None (applies) or the reason it does not."""
    results: dict[str, str | None] = {}
    with tempfile.TemporaryDirectory(prefix="seek-patch-check-") as tmp:
        single = single_apk(tc, apk, tmp, log)
        src = os.path.join(tmp, "src")
        decode(tc, single, src, resources=False)
        log(f"       version {decoded_version(src) or '?'}")
        tree = SmaliTree(src)
        missing = missing_native_libraries(single, tree)
        if missing:
            results["(apk)"] = f"native code missing: {', '.join(missing)} -- {_missing_hint(apk)}"
        for name, patch in BY_NAME.items():
            try:
                with tree.transaction():
                    patch.apply(tree, Options())
                    raise _Rollback
            except _Rollback:
                results[name] = None
            except PatchError as e:
                results[name] = str(e)
    return results


class _Rollback(Exception):
    pass


def patch_apk(tc: Toolchain, apk: str, out: str, plan: Plan, log: Callable[[str], None] = print) -> None:
    with tempfile.TemporaryDirectory(prefix="seek-patch-") as tmp:
        single = single_apk(tc, apk, tmp, log)
        src = os.path.join(tmp, "src")
        log(f"decode {'the merged apk' if single != apk else os.path.basename(apk)}"
            + (" (with resources, for --side-by-side)" if plan.side_by_side else ""))
        decode(tc, single, src, resources=plan.side_by_side)
        log(f"       version {decoded_version(src) or '?'}")
        tree = SmaliTree(src)
        missing = missing_native_libraries(single, tree)
        if missing:
            if bundle.is_bundle(apk):
                raise ApkError(f"{os.path.basename(apk)} has no split with {', '.join(missing)}: the merged app would "
                               "crash.  Use a bundle with the native code for your phone (arm64_v8a, armeabi_v7a).")
            raise ApkError(f"{os.path.basename(apk)} does not contain {', '.join(missing)}: it is probably the base apk "
                           "of a split install (the native code lives in a config split).  Use a complete "
                           "(universal) apk, or the whole bundle (.xapk / .apks / .apkm).")
        apply_patches(src, plan, log, tree)
        if plan.side_by_side:
            path = os.path.join(src, "AndroidManifest.xml")
            with open(path, encoding="utf-8") as f:
                xml = f.read()
            new_package = plan.package or manifest.package_of(xml) + ".patched"
            if not manifest.valid_package(new_package):
                raise ApkError(f"not a valid package name: {new_package}")
            xml, notes = manifest.rename(xml, new_package, plan.label)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
            log("rename " + "; ".join(notes))
        log("build  apktool b")
        unsigned = os.path.join(tmp, "unsigned.apk")
        build(tc, src, unsigned)
        log("sign   zipalign + uber-apk-signer")
        key = sign(tc, unsigned, out, log)
        log(f"       key: {key}")
