"""seek-patch command line: list, check, patch, doctor."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from . import __version__
from .apk import SEEK_PACKAGE, ApkError, Plan, app_info, check, patch_apk
from .axml import AxmlError
from .bundle import BundleError
from .manifest import ManifestError, valid_package
from .patches import ALL, BY_NAME, RECOMMENDED, Options, conflicts, every_patch, missing_requirements
from .smali import PatchError
from .toolchain import APKEDITOR, APKTOOL, SIGNER, Toolchain, ToolchainError, ensure_jar, find_java, home, java_major

DEFAULT_LABEL = "Seek (patched)"


def _log(line: str) -> None:
    print(line, flush=True)


def _info_or_warn(apk: str):
    try:
        info = app_info(apk)
    except (AxmlError, BundleError, OSError) as e:
        raise SystemExit(f"error: {e}") from None
    print(f"app    {info}")
    if info.package != SEEK_PACKAGE:
        print(f"warn   not {SEEK_PACKAGE}: the patches only know the Seek Thermal app", file=sys.stderr)
    return info


def cmd_list(_args) -> int:
    for p in ALL:
        star = "*" if p.RECOMMENDED else " "
        print(f"{star} {p.NAME:18} {p.VERSIONS:14} {p.SUMMARY}")
    print("\n* = applied by default (seek-patch patch APK); add others with -p NAME, or --all")
    return 0


def cmd_check(args) -> int:
    _info_or_warn(args.apk)
    tc = Toolchain.load(log=_log)
    results = check(tc, args.apk, _log)
    for name, why in results.items():
        print(f"  {'ok  ' if why is None else 'no  '} {name:18} {'' if why is None else why}")
    if "(apk)" in results:
        return 1
    ok = [n for n in BY_NAME if results.get(n) is None]
    if not ok:
        return 1
    if all(n in ok for n in RECOMMENDED):
        print(f"use    seek-patch patch {args.apk}")
    else:
        print(f"use    seek-patch patch {args.apk} " + " ".join(f"-p {n}" for n in ok if n in RECOMMENDED))
    return 0


def cmd_patch(args) -> int:
    if not os.path.isfile(args.apk):
        raise SystemExit(f"error: {args.apk}: no such file")
    names = every_patch() if args.all else (args.patch or RECOMMENDED)
    names = [p.NAME for p in ALL if p.NAME in names]  # canonical order, no duplicates
    for a, b in conflicts(names):
        raise SystemExit(f"error: {a} and {b} are alternatives: pick one")
    for a, b in missing_requirements(names):
        raise SystemExit(f"error: {a} needs {b}: add it")
    if not 1.0 < args.sharpness <= 16.0:
        raise SystemExit("error: --sharpness must be > 1 and <= 16 (2 = iOS look)")
    if not 10 <= args.video_qp <= 40:
        raise SystemExit("error: --video-qp must be 10 - 40 (lower = better)")
    if (args.package or args.label) and not args.side_by_side:
        raise SystemExit("error: --package / --label only apply with --side-by-side")
    if args.package and not valid_package(args.package):
        raise SystemExit(f"error: --package {args.package}: not a valid Android package name")
    info = _info_or_warn(args.apk)
    stem = os.path.splitext(args.apk)[0]
    out = args.out or f"{stem}-patched{'-side-by-side' if args.side_by_side else ''}.apk"
    if os.path.exists(out) and not args.force:
        raise SystemExit(f"error: {out} exists (use -f to replace it)")
    opts = Options(sharpness=args.sharpness, video_codec=args.video_codec, video_qp=args.video_qp)
    plan = Plan(names, opts, args.side_by_side, args.package,
                (args.label or DEFAULT_LABEL) if args.side_by_side else None,
                skip_unavailable=not (args.all or args.patch))  # the default set adapts to the version
    tc = Toolchain.load(log=_log)
    patch_apk(tc, args.apk, out, plan, _log)
    print(f"wrote  {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
    if args.install:
        return _install(out, info.package if not args.side_by_side else None)
    if not args.side_by_side:
        print(f"next   uninstall the store app first ({info.package}): it is signed with Seek's key, this build "
              "with yours.  Or rebuild with --side-by-side to keep both.")
    return 0


def _install(apk: str, replaces: str | None) -> int:
    adb = shutil.which("adb")
    if not adb:
        print("error: adb not found (Android platform-tools)", file=sys.stderr)
        return 2
    print(f"adb    install -r {os.path.basename(apk)}")
    r = subprocess.run([adb, "install", "-r", apk], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    print("       " + out.splitlines()[-1] if out else "")
    if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out and replaces:
        print(f"hint   the installed {replaces} has a different signature (the store build).  Uninstall it "
              f"first:  adb uninstall {replaces}  -- or rebuild with --side-by-side.", file=sys.stderr)
    return 0 if r.returncode == 0 and "Success" in out else 1


def cmd_doctor(_args) -> int:
    ok = True
    try:
        java, version = find_java()
        good = java_major(version) >= 11
        ok &= good
        print(f"{'ok  ' if good else 'FAIL'} java            {java}  ({version}){'' if good else '  -- need 11+'}")
    except ToolchainError as e:
        print(f"FAIL java            {e}")
        ok = False
    for jar in (APKTOOL, SIGNER, APKEDITOR):
        try:
            print(f"ok   {jar.name:15} {ensure_jar(jar, log=_log)}")
        except (ToolchainError, OSError) as e:
            print(f"FAIL {jar.name:15} {e}")
            ok = False
    if ok:
        tc = Toolchain.load(log=_log)
        try:
            print(f"ok   signing key     {tc.keystore(log=_log)}")
        except ToolchainError as e:
            print(f"FAIL signing key     {e}")
            ok = False
    adb = shutil.which("adb")
    print(f"{'ok  ' if adb else 'info'} adb             {adb or 'not found (only needed for --install)'}")
    print(f"     home            {home()}")
    return 0 if ok else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="seek-patch", description="Unofficial patches for the Seek Thermal Android app.")
    ap.add_argument("--version", action="version", version=f"seek-patch {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    sub.add_parser("list", help="list the patches").set_defaults(fn=cmd_list)
    c = sub.add_parser("check", help="dry run: which patches apply to an apk")
    c.add_argument("apk", help="the Seek Thermal .apk, or an .xapk / .apks / .apkm bundle")
    c.set_defaults(fn=cmd_check)
    p = sub.add_parser("patch", help="patch, rebuild and sign an apk",
                       description="Patch, rebuild and sign a Seek Thermal apk.  Default: "
                                   + ", ".join(RECOMMENDED) + ", skipping any that do not apply to the "
                                   "apk's version; patches named with -p must all apply.")
    p.add_argument("apk", help="the Seek Thermal .apk, or an .xapk / .apks / .apkm bundle (merged into one apk first)")
    p.add_argument("-p", "--patch", action="append", choices=list(BY_NAME), metavar="NAME",
                   help=f"apply this patch (repeatable); one of {', '.join(BY_NAME)}")
    p.add_argument("--all", action="store_true",
                   help="apply every patch, debug_log included, but not no_smoothing (the alternative to "
                        "smoothing_settings); all must apply")
    p.add_argument("--sharpness", type=float, default=Options.sharpness, metavar="N",
                   help="sharp_scaling: blend over 1/N of a pixel (2 = iOS look, higher = crisper)")
    p.add_argument("--video-codec", choices=["hevc", "avc"], default="hevc",
                   help="video_quality: codec tried first (hevc = smaller files; avc = H.264, plays everywhere)")
    p.add_argument("--video-qp", type=int, default=Options.video_qp, metavar="N",
                   help=f"video_quality: constant quantizer, lower = better and bigger (default {Options.video_qp})")
    p.add_argument("--side-by-side", action="store_true",
                   help="new package name + label, installs next to the store app (rebuilds resources)")
    p.add_argument("--package", help="package name for --side-by-side (default: <original>.patched)")
    p.add_argument("--label", help=f'launcher label for --side-by-side (default: "{DEFAULT_LABEL}")')
    p.add_argument("-o", "--out", help="output apk (default: <input>-patched.apk)")
    p.add_argument("-f", "--force", action="store_true", help="replace an existing output file")
    p.add_argument("--install", action="store_true", help="adb install the result")
    p.set_defaults(fn=cmd_patch)
    sub.add_parser("doctor", help="check Java, fetch the pinned tools, create the signing key").set_defaults(fn=cmd_doctor)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (PatchError, ApkError, BundleError, ManifestError, AxmlError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ToolchainError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
