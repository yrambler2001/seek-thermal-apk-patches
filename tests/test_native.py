"""smart_smoothing's native hook, built for the host with the system C compiler and driven by a
stand-in for the image library (tests/native/hook_host.c): it finds the first filter, clears alpf,
filters that filter's output in place, halves the estimate at a shutter event, leaves frames that are
not images alone, and is the library's own processing when off.

Opt-in, the research stage itself: SEEK_SUPERRES=<superres checkout> builds its tnr.c and compares on a
recorded burst (SEEK_BURST=<file.cube>, default: the first in data/bursts) -- the hooked path must give
the same pixels.  Needs `cc`; skipped otherwise."""
from __future__ import annotations

import glob
import math
import os
import random
import re
import shutil
import struct
import subprocess
from array import array
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
NATIVE = REPO / "helpers" / "native"
DRIVER = Path(__file__).resolve().parent / "native" / "hook_host.c"
CC = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
FLAGS = ["-O3", "-ffast-math", "-fno-finite-math-only", "-std=c11", "-w"]  # as the research host harness

pytestmark = pytest.mark.skipif(not CC, reason="no C compiler")


def _compile(out: Path, sources: list[Path], includes: list[Path], direct: bool = False) -> Path:
    cmd = [CC, *FLAGS, *(f"-I{i}" for i in includes), *(["-DDIRECT"] if direct else []), *map(str, sources),
           "-lm", "-o", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


@pytest.fixture(scope="module")
def drivers(tmp_path_factory):
    d = tmp_path_factory.mktemp("native")
    hook = _compile(d / "hook", [DRIVER, NATIVE / "smooth.c", NATIVE / "tnr.c"], [NATIVE])
    direct = _compile(d / "direct", [DRIVER, NATIVE / "tnr.c"], [NATIVE], direct=True)
    return hook, direct, d


def _run(exe: Path, frames: Path, w: int, h: int, n: int, out: Path, *args: str) -> str:
    r = subprocess.run([str(exe), str(frames), str(w), str(h), str(n), str(out), *args], capture_output=True,
                       text=True, check=True)
    return r.stdout


def _synthetic(path: Path, w: int = 206, h: int = 156, n: int = 24) -> None:
    """A warm blob and stripes drifting by sub-pixel steps, a level step at frame 12, sensor-like noise."""
    rnd = random.Random(7)
    data = array("H")
    for k in range(n):
        dx, dy, level = 0.37 * k, 0.21 * k, 8000 + (40 if k >= 12 else 0)
        for y in range(h):
            for x in range(w):
                u, v = x - dx, y - dy
                s = 600 * math.exp(-((u - 90) ** 2 + (v - 70) ** 2) / 900) + 80 * math.sin(u / 5) + 30 * math.cos(v / 9)
                data.append(int(level + s + rnd.gauss(0, 6)))
    path.write_bytes(data.tobytes())


@pytest.fixture(scope="module")
def frames(drivers):
    p = drivers[2] / "synthetic.u16"
    _synthetic(p)
    return p


def _counters(line: str) -> dict[str, int]:
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)}


def test_hook_filters_the_first_filter_like_the_stage(drivers, frames, tmp_path):
    hook, direct, _ = drivers
    a, b = tmp_path / "hook.u16", tmp_path / "direct.u16"
    c = _counters(_run(hook, frames, 206, 156, 24, a, "shutter=12"))
    _run(direct, frames, 206, 156, 24, b, "shutter=12")
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes() != frames.read_bytes()  # it did filter
    # found the filters on frame 0; alpf reached the first filter only then; one shutter halving
    assert c == {"frames": 23, "learned": 1, "shutters": 1, "other": 0, "alpf_seen": 1, "filter2": 24,
                 "shutter_calls": 2}


def test_hook_leaves_frames_that_are_not_images(drivers, frames, tmp_path):
    hook, direct, _ = drivers
    a, b = tmp_path / "hook.u16", tmp_path / "direct.u16"
    c = _counters(_run(hook, frames, 206, 156, 24, a, "other=9"))
    _run(direct, frames, 206, 156, 24, b, "other=9")
    assert a.read_bytes() == b.read_bytes()
    px = 206 * 156 * 2
    assert a.read_bytes()[9 * px:10 * px] == frames.read_bytes()[9 * px:10 * px]
    assert c["other"] == 1 and c["frames"] == 22


@pytest.mark.parametrize("options", [("lines=0",), ("edge=0",), ("lines=0", "edge=0")])
def test_stripe_and_edge_options(drivers, frames, tmp_path, options):
    hook, direct, _ = drivers
    a, b, default = tmp_path / "hook.u16", tmp_path / "direct.u16", tmp_path / "default.u16"
    _run(hook, frames, 206, 156, 24, a, *options)
    _run(direct, frames, 206, 156, 24, b, *options)
    _run(hook, frames, 206, 156, 24, default)
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes() != default.read_bytes()  # the option changed the filter


def test_options_change_between_frames(drivers, frames, tmp_path):
    hook, direct, _ = drivers
    a, b = tmp_path / "hook.u16", tmp_path / "direct.u16"
    c = _counters(_run(hook, frames, 206, 156, 24, a, "plain=10", "shutter=14"))
    _run(direct, frames, 206, 156, 24, b, "plain=10", "shutter=14")
    assert a.read_bytes() == b.read_bytes()  # restarted at frame 10 without stripes / edge
    assert c["frames"] == 23 and c["shutters"] == 1


def test_off_is_the_library_alone(drivers, frames, tmp_path):
    out = tmp_path / "off.u16"
    c = _counters(_run(drivers[0], frames, 206, 156, 24, out, "off=1", "shutter=5"))
    assert out.read_bytes() == frames.read_bytes()
    assert c["alpf_seen"] == 24 and c["frames"] == 0 and c["learned"] == 0 and c["shutter_calls"] == 2


def test_unknown_image_size_is_left_alone(drivers, tmp_path):
    p, out = tmp_path / "small.u16", tmp_path / "out.u16"
    _synthetic(p, 100, 80, 6)
    c = _counters(_run(drivers[0], p, 100, 80, 6, out))
    assert out.read_bytes() == p.read_bytes()
    assert c["frames"] == 0 and c["alpf_seen"] == 6


# opt-in: the research build's own stage on a recorded burst -------------------------------------

SUPERRES = os.environ.get("SEEK_SUPERRES")


def _cube_frames(path: str) -> tuple[bytes, int, int, int]:
    """The first filter's u16 frames (flag 0x08) of a superres .cube: header 512 bytes, 56 per frame."""
    data = open(path, "rb").read()
    off, out, size = 512, [], None
    while off + 56 <= len(data):
        h = struct.unpack_from("<14i", data, off)
        flags, w, ht, es = h[3], h[9], h[10], h[11]
        off += 56
        if off + w * ht * es > len(data):
            break
        if flags == 0x08 and es == 2:
            out.append(data[off:off + w * ht * 2])
            size = (w, ht)
        off += w * ht * es
    return b"".join(out), size[0], size[1], len(out)


@pytest.mark.skipif(not SUPERRES, reason="set SEEK_SUPERRES to the superres checkout")
def test_hook_matches_the_research_stage_on_a_burst(drivers, tmp_path):
    root = Path(os.path.expanduser(SUPERRES))
    burst = os.environ.get("SEEK_BURST") or sorted(glob.glob(str(root / "data" / "bursts" / "*.cube")))[0]
    research = root / "live" / "native" / "seekip"
    ref = _compile(tmp_path / "research", [DRIVER, research / "src" / "tnr" / "tnr.c"],
                   [research / "include" / "internal", research / "include"], direct=True)
    raw, w, h, n = _cube_frames(burst)
    frames = tmp_path / "burst.u16"
    frames.write_bytes(raw)
    at = str(n // 2)
    a, b = tmp_path / "hook.u16", tmp_path / "research.u16"
    c = _counters(_run(drivers[0], frames, w, h, n, a, f"shutter={at}"))
    _run(ref, frames, w, h, n, b, f"shutter={at}")
    assert (w, h) == (206, 156) and c["frames"] == n - 1 and c["shutters"] == 1
    assert a.read_bytes() == b.read_bytes(), f"{os.path.basename(burst)}: hooked path differs from the research stage"
