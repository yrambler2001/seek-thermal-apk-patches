# `sharp_scaling` — upscale like the iOS app

**Stock:** the 206×156 sensor image is stretched to the screen with plain bilinear filtering, which
reads as soft.  **Patched:** each sensor pixel stays sharp and only the middle half of the step to its
neighbour is blended — the kernel Seek's iOS app uses.

## Measuring it

A saved photo or screenshot is the sensor frame scaled up, so the scaling can be read back out of
it ([tools/measure_kernel.py](../tools/measure_kernel.py)):

1. fit the sensor-pixel ("texel") grid — pitch and offset per axis — by sampling the image at
   candidate texel centres and re-interpolating;
2. recover the sensor frame by sampling at the fitted centres (nearest, bilinear and the patched
   kernel all pass exactly through the texel values there);
3. solve by least squares how much each display pixel takes from the 4 nearest texels, per sub-texel
   position.

Weight of the *next* pixel B, at 8 positions between pixels A and B:

| position A→B | 0.06 | 0.19 | 0.31 | 0.44 | 0.56 | 0.69 | 0.81 | 0.94 |
|---|---|---|---|---|---|---|---|---|
| bilinear (theory) | 0.06 | 0.19 | 0.31 | 0.44 | 0.56 | 0.69 | 0.81 | 0.94 |
| Android 2.3.4, live view | 0.03 | 0.18 | 0.32 | 0.45 | 0.57 | 0.71 | 0.85 | 1.00 |
| Android 2.3.4, saved photo | 0.03 | 0.19 | 0.31 | 0.44 | 0.56 | 0.68 | 0.80 | 1.00 |
| **iOS 2.2.8.0, saved photo** | 0.01 | 0.07 | 0.18 | 0.38 | 0.60 | 0.79 | 0.92 | 1.00 |
| nearest 2× then bilinear (theory) | 0 | 0 | 0.125 | 0.375 | 0.625 | 0.875 | 1 | 1 |
| **Android + `sharp_scaling`, live view** | 0.00 | 0.01 | 0.14 | 0.38 | 0.64 | 0.88 | 0.99 | 1.00 |
| Android + `sharp_scaling`, saved photo | 0.00 | 0.03 | 0.18 | 0.41 | 0.64 | 0.87 | 0.98 | 1.00 |

(Values at the ends are pulled toward 0/1 by JPEG and by averaging over each eighth.)  The iOS
photo came from a Compact on the same firmware (1.3.0.0).  Its image library is 2.10.5.0 (Android
2.3.4 ships 2.11.3.2), which handles the smoothing feature identically, and the iOS app sets that
feature the same way — the processing is not the difference, the upscaling is.

In the stock app both the live view and the saved photo are bilinear: the thermal texture has
`GL_LINEAR` magnification, and the photo is drawn onto its canvas with a `FILTER_BITMAP_FLAG` paint.

## The patch

**Live view (and video), on the GPU.**  The thermal fragment shader remaps the sample position inside
each texel before the hardware's bilinear lookup ("sharp bilinear"):

```glsl
t = uv * size - 0.5;  i = floor(t);
f = clamp((t - i - 0.5) * sharpness + 0.5, 0.0, 1.0);   // 1 = bilinear, 2 = iOS, large = nearest
color = texture2D(thermalTexture, (i + f + 0.5) / size);
```

With sharpness 2 the blend runs over the middle half of each texel step, exactly the
"nearest 2× then bilinear" kernel, at no CPU cost (render-thread CPU 10.6 % of a core patched vs
11.4 % stock; a CPU version that uploaded a 2× nearest-upscaled texture cost ~10 % of a core more).

The shader needs the texture size, which GLSL ES 1.00 cannot query, so:

- the upload method records it (`SharpScale.size(w, h)` right before `glTexImage2D`), and
- a `thermalSize` uniform is set right before each `glDrawArrays` of the thermal program, with
  `thermalSharp`, the sharpness.  The locations are looked up on every draw (no cache): the video
  encoder may draw from another thread.

Texture coordinates move to `highp` — on Mali GPUs `mediump` is fp16, which would quantize the remap
to ~0.1 texel and show as stair steps.  `highp` is optional in fragment shaders on OpenGL ES 2.0; GPUs
without it (`GL_FRAGMENT_PRECISION_HIGH` undefined: Mali-400/450, early Tegra) compile the
`SHARP_OFF` branch and keep the stock bilinear sample, instead of showing artifacts.

**Saved photos, on the CPU.**  The photo method draws the frame bitmap onto a 1280×960 canvas with a
filtered paint.  The patch draws a `round(sharpness)`× (2 – 8) nearest-upscaled copy instead
(`Bitmap.createScaledBitmap(..., filter=false)`) with the same paint — the same kernel, once per
capture.

Image processing and temperatures are untouched.

## Settings

*Settings → Image & Video* gets two items (on every release the patch supports, 2.0 – 2.3.4):

| setting | default | |
|---|---|---|
| **iOS-style upscaling** | on | on: *iOS: each pixel stays sharp, blended only at its edges*; off: *Android: smooth bilinear, each pixel blended across its width* — the stock scaling, live view and photos |
| **Upscaling sharpness** | 2, or `--sharpness` | 1.5, 2 (iOS), 3, 4, 6, 8, each shown as the share of a pixel it blends over (2: 50 %); greyed out under Android |

`--sharpness N` (default 2) is where the sharpness starts, and it joins the list when it falls
between the choices; the setting then wins.  Changes show as soon as the live view is back.  The
values sit in seek-patch's preferences file; `seekpatch.Upscale` writes them to
`SharpScale.sharpness` (the uniform) and `SharpScale.photoFactor` (the photo).

Is sharpness 1 exactly bilinear?  Mathematically yes: `f` becomes the fraction of `t`, and the
coordinate comes back unchanged.  In floating point it comes back within rounding (~10⁻⁷ of a texel
in `highp`), not bit for bit.  So *Android* does not rely on it: at sharpness 1 or less the shader
returns the coordinate untouched, which is the stock sample exactly, with the same single shader.
The photo then gets the stock filtered draw (factor 1).

Measured on the Pixel (2.3.4, Compact) with `tools/measure_kernel.py` on live-view screenshots: the
weight of the next texel at sub-texel position 0.81 was 0.97 at sharpness 2, 1.00 at 8, and 0.83
with *Android* (bilinear: 0.81).
