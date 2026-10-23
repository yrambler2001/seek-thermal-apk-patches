#!/usr/bin/env python3
"""Render docs/data/kernels.json as the README's kernel chart, one SVG per color scheme.

    python3 tools/kernel_chart.py            -> docs/images/kernel-light.svg, kernel-dark.svg

Standard library only.  Colors: a validated categorical palette (slots 1-3, light and dark steps);
the line markers differ in shape too, so the series stay apart without color.
"""
from __future__ import annotations

import json
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "docs", "data", "kernels.json")
OUT = os.path.join(HERE, "..", "docs", "images")

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
                  series=["#2a78d6", "#eb6834", "#1baf7a"]),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
                 series=["#3987e5", "#d95926", "#199e70"]),
}
MARKERS = ["circle", "square", "diamond"]
W, H = 720, 430
L, R, T, B = 64, 24, 78, 64  # plot margins
FONT = 'font-family="system-ui, -apple-system, Segoe UI, sans-serif"'


def x_of(t: float) -> float:
    return L + t * (W - L - R)


def y_of(w: float) -> float:
    return H - B - w * (H - T - B)


def marker(kind: str, x: float, y: float, color: str, ring: str) -> str:
    r = 4.5
    if kind == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" stroke="{ring}" stroke-width="2"/>'
    if kind == "square":
        s = r * 1.8
        return (f'<rect x="{x - s / 2:.1f}" y="{y - s / 2:.1f}" width="{s:.1f}" height="{s:.1f}" rx="1.5" fill="{color}" '
                f'stroke="{ring}" stroke-width="2"/>')
    d = r * 1.45
    return (f'<path d="M{x:.1f} {y - d:.1f} L{x + d:.1f} {y:.1f} L{x:.1f} {y + d:.1f} L{x - d:.1f} {y:.1f} Z" '
            f'fill="{color}" stroke="{ring}" stroke-width="2"/>')


def render(data: dict, theme: dict) -> str:
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-labelledby="title desc">',
           '<title id="title">Upscaling kernel: weight of the next pixel vs position</title>',
           f'<desc id="desc">{escape(data["description"])}</desc>',
           f'<rect width="{W}" height="{H}" rx="12" fill="{theme["surface"]}"/>']
    # grid + axes
    for v in (0, 0.25, 0.5, 0.75, 1):
        y, x = y_of(v), x_of(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="{theme["grid" if v else "axis"]}" stroke-width="1"/>')
        out.append(f'<text x="{L - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="{theme["muted"]}" {FONT}>{v:g}</text>')
        out.append(f'<text x="{x:.1f}" y="{H - B + 20}" text-anchor="middle" font-size="12" fill="{theme["muted"]}" {FONT}>{v:g}</text>')
    out.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 16}" text-anchor="middle" font-size="13" fill="{theme["ink2"]}" {FONT}>'
               'position between two neighbouring pixels A → B</text>')
    out.append(f'<text x="18" y="{(T + H - B) / 2:.0f}" text-anchor="middle" font-size="13" fill="{theme["ink2"]}" {FONT} '
               f'transform="rotate(-90 18 {(T + H - B) / 2:.0f})">weight of pixel B</text>')
    # series
    for i, s in enumerate(data["series"]):
        color = theme["series"][i]
        pts = " ".join(f"{x_of(t):.1f},{y_of(w):.1f}" for t, w in zip(data["t"], s["w"]))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" '
                   'stroke-linecap="round"/>')
    for i, s in enumerate(data["series"]):
        for t, w in zip(data["t"], s["w"]):
            out.append(marker(MARKERS[i], x_of(t), y_of(w), theme["series"][i], theme["surface"]))
    # legend (identity never by color alone: marker shape + label)
    lx = L
    for i, s in enumerate(data["series"]):
        color = theme["series"][i]
        out.append(f'<line x1="{lx}" y1="34" x2="{lx + 26}" y2="34" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
        out.append(marker(MARKERS[i], lx + 13, 34, color, theme["surface"]))
        label = s["label"]
        out.append(f'<text x="{lx + 34}" y="38" font-size="13" fill="{theme["ink"]}" {FONT}>{escape(label)}</text>')
        lx += 34 + int(len(label) * 7.2) + 28
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    for name, theme in THEMES.items():
        path = os.path.join(OUT, f"kernel-{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(data, theme))
        print(f"wrote {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
