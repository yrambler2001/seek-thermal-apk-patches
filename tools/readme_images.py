#!/usr/bin/env python3
"""Build the README's smoothing figure: a colour photo of the board aligned to the thermal photos, next to
them (smoothing-photos.avif), and 2x crops of eight spots, the same spot across each row
(smoothing-crops.avif).  The two share their columns, so they stack into one figure.

    uv run --no-project --with numpy --with pillow --with opencv-python-headless \\
        python tools/readme_images.py --colour IMG.HEIC --off OFF.jpg --on ON.jpg \\
        --patched PATCHED.png --smart SMART.png [--out docs/images]

The four thermal photos are the app's own (img_thermal_*): stock with Image smoothing off and on,
seek-thermal-apk-patches at its defaults, and with Smart smoothing.  Needs ImageMagick (`magick`) for HEIC and
AVIF; every image is stripped of its metadata (an iPhone photo carries GPS).

Alignment:
- thermal to thermal: each photo is a hand-held shot of the same board, so each crop is placed by
  the hot chip's offset, then moved (within 24 px) to the best match of edges with the reference.
- colour to thermal: a homography found by ECC (OpenCV) between the thermal photo's local darkness
  and the colour photo's shiny metal.  Low-emissivity metal (SMD end caps, pads, inductor tops,
  connector pins) reads dark in thermal and bright grey in colour.  It starts from four parts
  matched by eye (MATCHES), which only need to be within a few pixels.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REF = "smart"
NAMES = ["off", "on", "patched", "smart"]
HEAD = [["colour photo"], ["stock,", "smoothing switch off"], ["stock,", "smoothing switch on"],
        ["seek-thermal-apk-patches,", "default settings", "(same as on the iOS app)"], ["seek-thermal-apk-patches,", "default settings", "+ Smart smoothing"]]
W, H = 150, 112   # crop size in thermal photo pixels; drawn at 2x
REGIONS = [       # label, crop's top-left relative to the hot chip in the reference photo
    ("A   the fan wire and the chip's lower left", -140, 10),
    ("B   the chip's top-right corner, SMDs", -20, -120),
    ("C   the chip's right edge, SMDs", 10, -10),
    ("D   SMDs right of the chip", 60, -100),
    ("E   the chip's top-left corner, SMDs", -120, -150),
    ("F   a row of SMDs", 120, 100),
    ("G   the fan wire on the flat board: grain", -250, -30),
    ("H   the chip's bottom-right corner, SMDs", -10, 10),
]
# reference thermal photo -> colour photo, four parts matched by eye: the hot QFN, the 1R0 inductor,
# the C1CAN chip, the fan connector
MATCHES = [((411.4, 411.4), (1385, 1399)), ((591.4, 702.9), (1640, 1817)),
           ((348.0, 956.6), (1264, 2200)), ((317.0, 745.7), (1252.6, 1882))]
GREY = "#7d8590"  # reads on GitHub's light and dark pages; the sheet's background is transparent
FONT = "/System/Library/Fonts/Helvetica.ttc"


def load(path: str, tmp: str) -> np.ndarray:
    """BGR pixels, upright (EXIF orientation applied), via ImageMagick."""
    out = os.path.join(tmp, os.path.basename(path) + ".png")
    subprocess.run(["magick", path, "-auto-orient", "-strip", out], check=True)
    return cv2.imread(out)


def avif(img: Image.Image | np.ndarray, path: str, pixels: bool) -> None:
    """Write AVIF the way CONTRIBUTING.md says: q45, or q75 4:4:4 for single pixels."""
    if isinstance(img, np.ndarray):
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        img.save(f.name)
        q = ["-quality", "75", "-define", "heic:chroma=444"] if pixels else ["-quality", "45"]
        subprocess.run(["magick", f.name, "-strip", *q, "-define", "heic:speed=2", path], check=True)
    print(path, os.path.getsize(path), "bytes")


def chip(bgr: np.ndarray) -> tuple[int, int]:
    """The hot chip: the centre of the brightest blob, the colour bar and readouts left out."""
    a = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(float)
    a[:, :40] = 0
    a[:150, 780:] = 0
    a[1180:, :] = 0
    ys, xs = np.nonzero(a >= np.percentile(a, 99.6))
    k = (abs(ys - np.median(ys)) < 120) & (abs(xs - np.median(xs)) < 120)
    return int(xs[k].mean()), int(ys[k].mean())


def edges(gray: np.ndarray, sigma: float = 0) -> np.ndarray:
    g = gray.astype(np.float32)
    if sigma:
        g = cv2.GaussianBlur(g, (0, 0), sigma)
    return cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))


def place(edge: np.ndarray, ref_edge: np.ndarray, guess: tuple[int, int], ref_box: tuple[int, int]) -> tuple[int, int]:
    """The crop's top-left in a photo: the guess, moved within 24 px to the best edge match."""
    rx, ry = ref_box
    ref = ref_edge[ry:ry + H, rx:rx + W]
    gx, gy = guess
    return max(((gx + sx, gy + sy) for sy in range(-24, 25) for sx in range(-24, 25)),
               key=lambda p: ncc(edge[p[1]:p[1] + H, p[0]:p[0] + W], ref))


def align_colour(thermal: np.ndarray, colour: np.ndarray) -> np.ndarray:
    """Homography thermal -> colour pixels (for warpPerspective with WARP_INVERSE_MAP)."""
    A, _ = cv2.estimateAffine2D(np.float32([m[0] for m in MATCHES]), np.float32([m[1] for m in MATCHES]))
    M = np.vstack([A, [0, 0, 1]]).astype(np.float32)
    hi, lo = colour.max(2).astype(np.float32), colour.min(2).astype(np.float32)
    metal = np.clip((hi - 110) / 90, 0, 1) * np.clip((60 - (hi - lo)) / 60, 0, 1)   # bright and grey
    lum = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dark = cv2.GaussianBlur(lum, (0, 0), 14) - lum                                  # locally dark
    mask = np.zeros(lum.shape, np.uint8)
    mask[170:1160, 110:720] = 255      # the board; not the colour bar and readouts
    mask[560:720, 390:570] = 0         # the spot meter
    mask[lum > 235] = 0                # the saturated chip
    size = (thermal.shape[1], thermal.shape[0])
    for sigma in (4.0, 2.5, 1.5):
        t = cv2.GaussianBlur(dark, (0, 0), sigma)
        v = cv2.GaussianBlur(cv2.warpPerspective(metal, M, size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP),
                             (0, 0), sigma)
        cc, D = cv2.findTransformECC(t, v, np.eye(3, dtype=np.float32), cv2.MOTION_HOMOGRAPHY,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 500, 1e-7), mask, 1)
        M = (M @ D).astype(np.float32)
        print(f"colour alignment, blur {sigma}: correlation {cc:.3f}")
    return M.astype(np.float64)


def colour_view(colour: np.ndarray, M: np.ndarray, x: float, y: float, w: int, h: int, scale: float) -> Image.Image:
    """The colour photo as it falls in the thermal box (x, y, w, h), scale output pixels per thermal pixel."""
    T = np.array([[1 / scale, 0, x], [0, 1 / scale, y], [0, 0, 1]])
    out = cv2.warpPerspective(colour, M @ T, (int(w * scale), int(h * scale)), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
    return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))


GAP = 6           # between columns; both images share the grid, so they stack into one figure


def header_font() -> ImageFont.FreeTypeFont:
    size = 24   # the largest that fits every header line in its column
    while any(ImageFont.truetype(FONT, size, index=1).getlength(text) > 2 * W - 8 for lines in HEAD for text in lines):
        size -= 1
    return ImageFont.truetype(FONT, size, index=1)


def photos(images: list[Image.Image]) -> Image.Image:
    """The column headers over the whole photos, one per column, 2W wide."""
    head, line = header_font(), 30
    top = max(len(h) for h in HEAD) * line + 14
    ph = round(images[0].height * 2 * W / images[0].width)
    s = Image.new("RGBA", (len(HEAD) * (2 * W + GAP) - GAP, top + ph), (0, 0, 0, 0))
    dr = ImageDraw.Draw(s)
    for i, (lines, im) in enumerate(zip(HEAD, images)):   # bottom-aligned over the photos
        for k, text in enumerate(lines):
            dr.text((i * (2 * W + GAP) + W, top - 8 - (len(lines) - k) * line), text, fill=GREY, font=head, anchor="mt")
        s.paste(im.convert("RGB").resize((2 * W, ph), Image.LANCZOS), (i * (2 * W + GAP), top))
    return s


def sheet(rows: list[list[Image.Image]]) -> Image.Image:
    """The crops, a labelled row per region, in the columns of photos()."""
    label = ImageFont.truetype(FONT, 23)
    lab, rowgap = 34, 12
    s = Image.new("RGBA", (len(HEAD) * (2 * W + GAP) - GAP, rowgap + len(rows) * (lab + 2 * H + rowgap)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(s)
    for r, ((text, _, _), row) in enumerate(zip(REGIONS, rows)):
        y = rowgap + r * (lab + 2 * H + rowgap)
        dr.text((2, y + 4), text, fill=GREY, font=label)
        for i, c in enumerate(row):
            s.paste(c, (i * (2 * W + GAP), y + lab))
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--colour", required=True)
    for n in NAMES:
        ap.add_argument(f"--{n}", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "images"))
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        photo = {n: load(getattr(a, n), tmp) for n in NAMES}
        colour = load(a.colour, tmp)
    centre = {n: chip(photo[n]) for n in NAMES}
    edge = {n: edges(cv2.cvtColor(photo[n], cv2.COLOR_BGR2GRAY)) for n in NAMES}
    M = align_colour(photo[REF], colour)
    rows = []
    for _, dx, dy in REGIONS:
        ref_box = (centre[REF][0] + dx, centre[REF][1] + dy)
        row = [colour_view(colour, M, *ref_box, W, H, 2)]
        for n in NAMES:
            x, y = ref_box if n == REF else place(edge[n], edge[REF], (centre[n][0] + dx, centre[n][1] + dy), ref_box)
            crop = Image.fromarray(cv2.cvtColor(photo[n][y:y + H, x:x + W], cv2.COLOR_BGR2RGB))
            row.append(crop.resize((2 * W, 2 * H), Image.NEAREST))
        rows.append(row)
    full = colour_view(colour, M, 0, 0, photo[REF].shape[1], photo[REF].shape[0], 2)
    full = full.resize((photo[REF].shape[1], photo[REF].shape[0]), Image.LANCZOS)
    whole = [full] + [Image.fromarray(cv2.cvtColor(photo[n], cv2.COLOR_BGR2RGB)) for n in NAMES]
    avif(photos(whole), os.path.join(a.out, "smoothing-photos.avif"), pixels=False)
    avif(sheet(rows), os.path.join(a.out, "smoothing-crops.avif"), pixels=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
