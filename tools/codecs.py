#!/usr/bin/env python3
"""What the phone's video encoders can do, and what each QP costs and keeps.

    python3 tools/codecs.py list                     # encoders: hardware?, rate control, 4:4:4 profiles, sizes
    python3 tools/codecs.py ladder REF.mp4           # re-encode REF's frames at a QP ladder and score them

`ladder` wants a recording much better than the candidates -- record 10+ s of the scene you care
about at Video quality 40 Mbit/s, the top of the app's list.  Its frames are decoded here, pushed to the phone, encoded there by
each hardware HEVC / H.264 encoder at every QP (set up as video_quality does), pulled back and scored
against REF: bitrate, PSNR (luma, chroma), SSIM, and how much of the sensor's frame-to-frame noise is
kept (100 % = as in REF; lower = the encoder smooths it away).

Needs adb, a JDK (javac), the Android SDK (ANDROID_HOME: build-tools d8, platforms;android-35),
ffmpeg, and numpy for `ladder`.  The Java sources are next to this file, in codecs/.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = "android-35"
REMOTE = "/data/local/tmp/seek-thermal-apk-patches-codecs"


def sh(cmd: list[str], **kw) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"{' '.join(cmd[:3])} ...: {r.stdout}{r.stderr}")
    return r.stdout


def build_dex(tmp: str) -> str:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or "/opt/homebrew/share/android-commandlinetools"
    android_jar = os.path.join(sdk, "platforms", PLATFORM, "android.jar")
    d8s = sorted(glob.glob(os.path.join(sdk, "build-tools", "*", "d8")))
    javac = shutil.which("javac", path=os.path.join(os.environ.get("JAVA_HOME", ""), "bin")) or shutil.which("javac")
    if not (os.path.exists(android_jar) and d8s and javac):
        sys.exit(f"need javac, and in the Android SDK ({sdk}) build-tools and platforms;{PLATFORM}")
    classes = os.path.join(tmp, "classes")
    sh([javac, "-source", "11", "-target", "11", "-Xlint:-options", "-cp", android_jar, "-d", classes,
        *glob.glob(os.path.join(HERE, "codecs", "*.java"))])
    sh([d8s[-1], "--min-api", "31", "--lib", android_jar, "--output", tmp, *glob.glob(os.path.join(classes, "*.class"))])
    return os.path.join(tmp, "classes.dex")


def run_on_phone(dex: str, *args: str) -> str:
    sh(["adb", "shell", "mkdir", "-p", REMOTE])
    sh(["adb", "push", dex, f"{REMOTE}/tools.dex"])
    return sh(["adb", "shell", f"CLASSPATH={REMOTE}/tools.dex app_process / " + " ".join(args)])


def hardware_encoders(listing: str) -> list[tuple[str, str]]:
    found = re.findall(r"^(\S+)  (video/hevc|video/avc)  hardware$", listing, re.M)
    return sorted(found, key=lambda e: e[1] != "video/hevc")


def cmd_list(_a) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        print(run_on_phone(build_dex(tmp), "Encoders"), end="")
    sh(["adb", "shell", "rm", "-rf", REMOTE])


def cmd_ladder(a) -> None:
    import numpy as np

    probe = sh(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height,avg_frame_rate",
                "-of", "csv=p=0", a.ref]).strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    num, den = probe[2].split("/")
    fps = float(num) / float(den)
    qps = [int(q) for q in a.qp.split(",")]
    fs = w * h * 3 // 2
    with tempfile.TemporaryDirectory(prefix="seek-thermal-apk-patches-ladder-") as tmp:
        dex = build_dex(tmp)
        encoders = hardware_encoders(run_on_phone(dex, "Encoders"))
        if not encoders:
            sys.exit("no hardware HEVC / H.264 encoder found")
        ref = os.path.join(tmp, "ref.yuv")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", str(a.skip), "-i", a.ref, "-frames:v", str(a.frames),
            "-f", "rawvideo", "-pix_fmt", "yuv420p", ref])
        frames = os.path.getsize(ref) // fs
        sh(["adb", "push", ref, f"{REMOTE}/ref.yuv"])
        ry = np.fromfile(ref, np.uint8).reshape(frames, fs).astype(np.float32)

        def noise(y):  # mean temporal standard deviation of the luma, overlays excluded
            y = y[:, : w * h].reshape(frames, h, w)[:, h // 12: h - h // 12, w // 8: w - w // 32]
            return (y - y.mean(0)).std(0).mean()

        ref_noise = noise(ry)
        print(f"reference {a.ref}: {w}x{h}, {frames} frames at {fps:.1f} fps")
        print(f"{'encoder':28} {'QP':>3} {'Mbit/s':>7} {'MB/min':>7} {'PSNR Y':>7} {'PSNR UV':>8} {'SSIM':>7} {'noise kept':>10}")
        for name, mime in encoders:
            for qp in qps:
                remote = f"{REMOTE}/{name}-{qp}.mp4"
                run_on_phone(dex, "Ladder", f"{REMOTE}/ref.yuv", str(w), str(h), str(frames), f"{fps:.3f}", name, mime,
                             str(qp), remote)
                mp4, raw = os.path.join(tmp, "enc.mp4"), os.path.join(tmp, "enc.yuv")
                sh(["adb", "pull", remote, mp4])
                sh(["adb", "shell", "rm", remote])
                sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-f", "rawvideo", "-pix_fmt", "yuv420p", raw])
                ey = np.fromfile(raw, np.uint8).reshape(-1, fs)[:frames].astype(np.float32)
                y, c = slice(0, w * h), slice(w * h, fs)
                psnr_y = 10 * np.log10(255 ** 2 / ((ey[:, y] - ry[:, y]) ** 2).mean())
                psnr_c = 10 * np.log10(255 ** 2 / ((ey[:, c] - ry[:, c]) ** 2).mean())
                raw_in = ["-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{w}x{h}", "-r", "25", "-i"]
                out = subprocess.run(["ffmpeg", "-v", "info", *raw_in, raw, *raw_in, ref, "-lavfi", "ssim", "-f", "null", "-"],
                                     capture_output=True, text=True).stderr
                ssim = float(re.search(r"All:([0-9.]+)", out).group(1))
                mbit = os.path.getsize(mp4) * 8 / (frames / fps) / 1e6
                print(f"{name:28} {qp:3d} {mbit:7.1f} {mbit * 60 / 8:7.0f} {psnr_y:7.2f} {psnr_c:8.2f} {ssim:7.4f} "
                      f"{noise(ey) / ref_noise:10.1%}", flush=True)
    sh(["adb", "shell", "rm", "-rf", REMOTE])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="the phone's encoders").set_defaults(fn=cmd_list)
    lad = sub.add_parser("ladder", help="score a QP ladder against a reference recording")
    lad.add_argument("ref", help="a high-quality recording (Video quality 40 Mbit/s)")
    lad.add_argument("--qp", default="14,16,18,20,22,24,26,28", help="comma-separated QPs (default %(default)s)")
    lad.add_argument("--frames", type=int, default=120, help="frames to use (default %(default)s)")
    lad.add_argument("--skip", type=float, default=2.0, help="seconds to skip at the start (default %(default)s)")
    lad.set_defaults(fn=cmd_ladder)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
