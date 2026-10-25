# `calibration` — your own linear correction of every temperature

**Stock:** the temperatures are the camera's factory calibration, with emissivity as the only
setting.  If a reference thermometer, or ice water and boiling water, says the readings are off,
there is nothing to set.
**Patched:** a **k·x+b** button floats below the top bar, on the left.  Tap it and enter two
numbers: **shown = k × measured + b**.  *k* is the gain (1: none), *b* the offset (0: none) in the
app's unit.  From the next frame on every temperature the app shows or saves is corrected, and the
button reads the correction, for example *1.02x − 0.5°C*.  *Reset* sets k = 1, b = 0.

- **What it applies to:** every temperature: the spot readout, the minimum and maximum (and their
  markers), the temperature bar, the radiometric data saved with *Store All Thermal Data*, and the
  coloring modes that work in degrees (Span & Level, the isotherm modes), which see the corrected
  values, so a span set at 30 °C means a corrected 30 °C.
- **What it doesn't change:** the automatic coloring.  It spreads the palette over the frame's raw
  sensor values, so the picture looks the same with or without a correction.  `lock_range` is not
  affected either.
- **It stays set** until changed, across app restarts and camera reconnects.  A saved photo keeps
  the corrected values, without a note of the correction.
- **The unit:** k is the same in °C, °F and K; b is entered and shown in the app's unit and kept in
  °C, so the correction holds when the unit is switched (1.02x + 0.5°C reads 1.02x + 0.26°F).
- **k must be above 0** (a negative gain would swap hot and cold).

A long press explains the button.

### Finding k and b

Measure two surfaces of known temperature far apart (a reference thermometer's probe on a matt,
high-emissivity surface; ice water and hot water in a matt cup), with the correction reset.  With
measured readings m₁, m₂ for true temperatures t₁, t₂:

    k = (t₂ − t₁) / (m₂ − m₁)        b = t₁ − k × m₁

With one reference only, keep k = 1 and set b = t − m.

## How it works

The image library (libseekip) turns each frame into degrees in `thermography_process`: per pixel
(from the sensor's counts, through the factory calibration and the emissivity), then the spot (a
trimmed mean of the central 6 × 6 pixels), the minimum and the maximum.  The app reads all of it
from there, and so does the library's own temperature coloring later in the same frame.

The patch's native library, `libseekpatch_calib.so`, points libseekip's PLT slot for
`thermography_process` at a wrapper.  The wrapper calls the original, then maps its outputs in
place: each pixel of the active window (float degrees, or the 16-bit `(t + 40) × 64` format), the
spot when it was measured, the minimum and maximum when they were (rounded to 0.1 as the library
rounds them).  The library's own state (its minimum / maximum hysteresis between frames) stays in
measured degrees, so the correction never compounds.  The output unit the library was asked for is
read every frame (thermography feature 50029) and b converted, so k × t + b holds in °C whatever it
is.  With k = 1 and b = 0 the library is not even hooked.

The patch adds:

| where | what |
|---|---|
| `lib/<abi>/libseekpatch_calib.so` | the wrapper and the hook; before changing anything it checks that the slot holds libseekip's own `thermography_process`, and that it and `thermography_getfeature` have the sizes of a verified build (the wrapper relies on their frame layout and features) |
| the camera screen, after `setContentView` | `seekpatch.Calib.attach`: the button, in the frame layout that holds the top bar, just after it, on the left |
| right after the per-frame feature-900 call | `Calib.frame()`: hooks the library once a correction is set, then passes changes on |

k and b live in the app's preferences (`seekpatch`: `calibration_k`, `calibration_b`, in °C).

## Versions

2.2.3 – 2.3.4: libseekip 2.11.3.2 calls `thermography_process` through its PLT; 2.2.0 – 2.2.2's
library (2.10.5.0) calls it directly, so there is nothing to hook.  The hook knows the library of
arm64-v8a (2.2.3 – 2.3.0 and 2.3.1 – 2.3.4) and armeabi-v7a (2.2.3 – 2.3.0, 2.3.3 – 2.3.4); on any
other library it changes nothing and the button says it is not available.  Built for arm64-v8a and
armeabi-v7a only.

Run on a phone with 2.3.4 arm64 (Pixel 8 Pro, Seek Compact, °C), switching the correction within a
few seconds (the temperature bar's maximum / the spot / the bar's minimum, as the app writes them):
none 18 / 18 / 17 °C; b = 10: 28 / 28 / 27 °C; none 20 / 19 / 18 °C; k = 2: 38 / 36 / 34 °C; none
19 / 19 / 17 °C.  The picture's colors did not change.  k = 1.02, b = −0.5 survived closing and
reopening the app (the button reads *1.02x − 0.5°C*, the library is hooked again at the first
frame).  armeabi-v7a, °F / K and saved photos have not been run on a phone.

Sources: [`helpers/native/calib.c`](../helpers/native/calib.c) (the PLT code it shares with the
other hooks is in [`plt.c`](../helpers/native/plt.c)),
[`helpers/java/seekpatch/Calib.java`](../helpers/java/seekpatch/Calib.java).
