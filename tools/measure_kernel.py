#!/usr/bin/env python3
"""How was a thermal frame scaled up?  Measure it from a screenshot or a saved photo.

    pip install numpy pillow        (or: pip install -e '.[measure]')
    python3 tools/measure_kernel.py IMAGE [--crop X0,Y0,X1,Y1] [--sensor 156x206]

1. Fit the sensor-pixel ("texel") grid per axis: sample the image at candidate texel centres,
   re-interpolate, keep the pitch/offset that reproduces the image best.
2. Recover the sensor-sized frame by sampling at the fitted texel centres -- nearest, bilinear and
   sharp-bilinear upscales all pass exactly through the texel values there.
3. Solve, per sub-texel position t, the weights the image gives the 4 nearest texels (least
   squares).  Bilinear: w(A) = 1 - t, w(B) = t.  Nearest: a step at t = 0.5.

Also prints "texel detail": how much pixel-level structure the recovered frame has (std of the
frame minus a 1-texel blur), relative to the scene's contrast -- what the camera's smoothing
filters take away.

--crop selects the thermal view (e.g. a phone screenshot without the app's chrome); the default
uses the whole image.  --sensor is the frame size as displayed (156x206 = a Compact in portrait).
Keep overlays (palette bar, spot readout) out of the measured band with --rows / --cols.
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image, ImageOps


def resample(a: np.ndarray, pos: np.ndarray, axis: int, method: str) -> np.ndarray:
    """Evaluate a along axis at fractional texel positions pos."""
    n = a.shape[axis]
    i0 = np.floor(pos + (0.5 if method == "nearest" else 0.0)).astype(int)
    shape = [1] * a.ndim
    shape[axis] = -1
    if method == "nearest":
        return np.take(a, np.clip(i0, 0, n - 1), axis=axis)
    t = (pos - i0).reshape(shape)
    lo = np.take(a, np.clip(i0, 0, n - 1), axis=axis)
    hi = np.take(a, np.clip(i0 + 1, 0, n - 1), axis=axis)
    return lo * (1 - t) + hi * t


def texel_pos(n_img: int, pitch: float, off: float) -> np.ndarray:
    return (np.arange(n_img) + 0.5 - off) / pitch - 0.5


def centre_pos(n_src: int, pitch: float, off: float) -> np.ndarray:
    return (np.arange(n_src) + 0.5) * pitch + off - 0.5


def fit_axis(lum: np.ndarray, axis: int, n_src: int) -> tuple[float, float, str, float]:
    """(pitch, offset, best-fitting method, error) of the texel grid along axis."""
    lines = (lum if axis == 1 else lum.T)[::5]
    n_img = lines.shape[1]
    nominal = n_img / n_src
    lo, hi = int(0.1 * n_img), int(0.9 * n_img)
    best = None
    for method in ("nearest", "bilinear"):
        for pitch in np.linspace(nominal * 0.97, nominal * 1.03, 61):
            for off in np.linspace(-pitch / 2, pitch / 2, 25):
                src = resample(lines, centre_pos(n_src, pitch, off), 1, "bilinear")
                rec = resample(src, texel_pos(n_img, pitch, off), 1, method)
                err = float(np.abs(rec[:, lo:hi] - lines[:, lo:hi]).mean())
                if best is None or err < best[3]:
                    best = (float(pitch), float(off), method, err)
    return best


def blur1(a: np.ndarray) -> np.ndarray:
    """Separable Gaussian, sigma = 1 texel."""
    k = np.exp(-0.5 * np.arange(-3, 4) ** 2)
    k /= k.sum()
    pad = np.pad(a, 3, mode="edge")
    a = sum(k[i] * pad[i:i + a.shape[0], 3:-3] for i in range(7))
    pad = np.pad(a, ((0, 0), (3, 3)), mode="edge")
    return sum(k[i] * pad[:, i:i + a.shape[1]] for i in range(7))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("image")
    ap.add_argument("--crop", help="X0,Y0,X1,Y1 of the thermal view in the image")
    ap.add_argument("--sensor", default="156x206", help="displayed frame size WxH (default 156x206)")
    ap.add_argument("--rows", default="0.05,0.40", help="band of rows (fractions) used for the kernel")
    ap.add_argument("--cols", default="0.17,0.97", help="band of columns (fractions) used for the kernel; the default "
                    "skips the Seek app's palette bar on the left")
    ap.add_argument("--bins", type=int, default=8, help="sub-texel positions to solve")
    a = ap.parse_args()

    img = ImageOps.exif_transpose(Image.open(a.image)).convert("RGB")
    if a.crop:
        img = img.crop(tuple(int(v) for v in a.crop.split(",")))
    lum = np.asarray(img, dtype=np.float64).mean(axis=2)
    h, w = lum.shape
    sw, sh = (int(v) for v in a.sensor.lower().split("x"))
    px, ox, mx, ex = fit_axis(lum, 1, sw)
    py, oy, my, ey = fit_axis(lum, 0, sh)
    print(f"{a.image}: {w}x{h}, texel grid x pitch {px:.3f} offset {ox:+.2f} (fits {mx}, err {ex:.2f}),"
          f" y pitch {py:.3f} offset {oy:+.2f} (fits {my}, err {ey:.2f})")

    r0, r1 = (float(v) for v in a.rows.split(","))
    rows = lum[int(r0 * h):int(r1 * h)]
    T = resample(rows, centre_pos(sw, px, ox), 1, "bilinear")
    pos = texel_pos(w, px, ox)
    i0 = np.floor(pos).astype(int)
    t = pos - i0
    c0, c1 = (float(v) for v in a.cols.split(","))
    ok = (i0 >= max(1, int(c0 * sw))) & (i0 <= min(sw - 3, int(c1 * sw)))
    print("\n  t (A->B)   w(A)    w(B)    | bilinear w(A) / w(B)")
    for b in range(a.bins):
        xs = np.nonzero(ok & (t >= b / a.bins) & (t < (b + 1) / a.bins))[0]
        A = np.stack([T[:, i0[xs] + d].ravel() for d in (-1, 0, 1, 2)] + [np.ones(rows.shape[0] * len(xs))], axis=1)
        wts = np.linalg.lstsq(A, rows[:, xs].ravel(), rcond=None)[0]
        tc = (b + 0.5) / a.bins
        print(f"   {tc:.3f}     {wts[1]:+.2f}   {wts[2]:+.2f}    |   {1 - tc:.2f} / {tc:.2f}")

    src = resample(resample(lum, centre_pos(sw, px, ox), 1, "bilinear"), centre_pos(sh, py, oy), 0, "bilinear")
    inner = src[8:-8, 8:-8]
    detail = float((inner - blur1(src)[8:-8, 8:-8]).std())
    print(f"\n  texel detail {detail:.2f} grey levels = {100 * detail / float(inner.std()):.1f}% of the scene contrast")


if __name__ == "__main__":
    main()
