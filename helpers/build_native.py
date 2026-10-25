#!/usr/bin/env python3
"""Build the native helpers (helpers/native) into the libraries the patches add to the app
(src/seekpatch/native/<abi>/): libseekpatch_smooth.so (smart_smoothing), libseekpatch_lock.so
(lock_range) and libseekpatch_calib.so (calibration).  They are committed, so patching needs no NDK;
run this after changing helpers/native (--check: are the committed libraries what the sources build --
the build is reproducible).

Needs the Android NDK r25b (--ndk, ANDROID_NDK_HOME, or ~/toolchains/android-ndk-r25b):
    clang -O3 -ffast-math -fno-finite-math-only, API 23, stripped, sha1 build id, 16 KiB pages
"""
from __future__ import annotations

import argparse
import filecmp
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(HERE, "native")
OUT = os.path.join(REPO, "src", "seekpatch", "native")
NDK_REVISION = "25.1.8937393"  # r25b
API = 23  # the Seek app's minSdkVersion
LIBRARIES = {"libseekpatch_smooth.so": ["tnr.c", "smooth.c", "smooth_android.c", "plt.c"],
             "libseekpatch_lock.so": ["lock.c", "plt.c"],
             "libseekpatch_calib.so": ["calib.c", "plt.c"]}
TARGETS = {"arm64-v8a": "aarch64-linux-android", "armeabi-v7a": "armv7a-linux-androideabi"}
CFLAGS = ["-O3", "-ffast-math", "-fno-finite-math-only", "-fPIC", "-fvisibility=hidden", "-ffunction-sections",
          "-fdata-sections", "-DNDEBUG", "-std=c11", "-Wall", "-Wextra", "-Werror=implicit-function-declaration"]
LDFLAGS = ["-shared", "-s", "-Wl,--gc-sections", "-Wl,--build-id=sha1", "-Wl,-z,max-page-size=16384",
           "-Wl,-z,relro", "-Wl,-z,now", "-Wl,--no-undefined", "-llog", "-lm"]


def ndk_root(arg: str | None) -> str:
    for root in (arg, os.environ.get("ANDROID_NDK_HOME"), os.environ.get("ANDROID_NDK_ROOT"),
                 os.path.expanduser("~/toolchains/android-ndk-r25b")):
        if root and os.path.isdir(root):
            with open(os.path.join(root, "source.properties"), encoding="utf-8") as f:
                m = re.search(r"Pkg\.Revision\s*=\s*([\d.]+)", f.read())
            if not m or m.group(1) != NDK_REVISION:
                sys.exit(f"{root}: NDK {m.group(1) if m else '?'}, need r25b ({NDK_REVISION}) for identical output")
            return root
    sys.exit("no NDK r25b: set ANDROID_NDK_HOME or pass --ndk")


def clang(ndk: str) -> str:
    host = {"Darwin": "darwin-x86_64", "Linux": "linux-x86_64", "Windows": "windows-x86_64"}[platform.system()]
    return os.path.join(ndk, "toolchains", "llvm", "prebuilt", host, "bin", "clang.exe" if os.name == "nt" else "clang")


def build(ndk: str, out: str) -> list[str]:
    """Build every ABI into out/<abi>/; returns the relative paths written."""
    cc = clang(ndk)
    written = []
    with tempfile.TemporaryDirectory(prefix="seek-patch-native-") as tmp:
        for abi, triple in TARGETS.items():
            os.makedirs(os.path.join(out, abi), exist_ok=True)
            for library, sources in LIBRARIES.items():
                objs = []
                for src in sources:
                    obj = os.path.join(tmp, f"{abi}-{src}.o")
                    if not os.path.exists(obj):
                        cmd = [cc, f"--target={triple}{API}", *CFLAGS, f"-ffile-prefix-map={SRC}=.", "-c", src, "-o", obj]
                        r = subprocess.run(cmd, cwd=SRC, capture_output=True, text=True)
                        if r.returncode != 0 or r.stderr.strip():
                            sys.exit(f"{abi} {src}:\n{r.stdout}{r.stderr}")
                    objs.append(obj)
                so = os.path.join(out, abi, library)
                r = subprocess.run([cc, f"--target={triple}{API}", *objs, *LDFLAGS, "-o", so], capture_output=True, text=True)
                if r.returncode != 0:
                    sys.exit(f"{abi} {library} link:\n{r.stdout}{r.stderr}")
                written.append(f"{abi}/{library}")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ndk", help="NDK r25b root (default: ANDROID_NDK_HOME, ~/toolchains/android-ndk-r25b)")
    ap.add_argument("--check", action="store_true", help="fail if the committed libraries are not what the sources build")
    a = ap.parse_args()
    ndk = ndk_root(a.ndk)
    if not a.check:
        names = build(ndk, OUT)
        print(f"wrote {', '.join(names)} in {os.path.relpath(OUT, REPO)}")
        return
    with tempfile.TemporaryDirectory(prefix="seek-patch-native-check-") as tmp:
        names = build(ndk, tmp)
        stale = [n for n in names if not os.path.exists(os.path.join(OUT, n))
                 or not filecmp.cmp(os.path.join(tmp, n), os.path.join(OUT, n), False)]
        if stale:
            sys.exit("native libraries out of date (run helpers/build_native.py): " + ", ".join(stale))
        print(f"native libraries up to date ({len(names)} files)")
    shutil.rmtree(os.path.join(HERE, "__pycache__"), ignore_errors=True)


if __name__ == "__main__":
    main()
