# `flat_field` — a button that flattens a warm camera's gradient

**Stock:** once the camera has warmed unevenly, every picture carries its gradient: brighter edges
and a darker middle, even on a uniform wall.  Nothing makes it go away until the camera cools down.
**Patched:** a **Flat field** button in the top bar.  Point the camera at a uniform surface (a wall,
a ceiling, a closed door) and tap it.  About 1.5 s later the gradient is gone.

| before the tap: 52 – 66 °F across a uniform surface | after: 65 °F everywhere |
|:---:|:---:|
| ![live view of a uniform surface with a warm-camera gradient](images/flat-field-before.avif) | ![the same surface after one tap](images/flat-field-after.avif) |

<sub>Seek Compact on a Pixel 8 Pro, app 2.3.4, Iron palette, the same scene before and 15 s after the
tap; each shot auto-ranges its own colour span.  What is left after the tap is sensor noise and the
row pattern.  The strip down the left edge has a sharp border, which the 16-pixel map cannot
follow.</sub>

While it works the button reads *Hold still…*; a toast says *Flat field set*.  A long press
explains what to do.  The correction lasts until the camera is reconnected or the app restarts;
then tap again.  If the camera was not pointed at a uniform surface, that scene is baked in: tap
again on one that is.

## Why the stock app keeps the gradient

The image library (libseekip) already has a runtime flat field: the **gradient stage**
(`gradient_process`, filter bit `0x80`, on in both "Image smoothing" positions).  It subtracts a
smooth correction map from every frame.  It learns that map only from frames that already look
flat.  On each frame, measured before correction:

1. It splits the frame into 16 × 16 blocks, averages each one, and measures the spread of the
   sixteen 4 × 4 sub-block means inside each block.
2. It runs two tests:

   | metric | meaning | passes when |
   |---|---|---|
   | `max_range` | the largest spread inside any block: detail | `< grad_p0` (feature 30100) |
   | `scaled_gradient` | the largest step between neighbouring block means, divided by the camera's response: `(step << 16) / scale`, where `scale` = response / 10 × 256 | `<= grad_p1` (feature 30102) |

   Blocks outside the viewable area (`block_map`) are left out of both tests.
3. If both pass, or the **force** flag (feature 30105) is set, it blends the frame's shape into the
   map.  The shape is the block means, upscaled to a smooth full-size surface, minus the centre
   block's mean:

   ```c
   ref = (7 * ref + (surface - centre)) >> 3;      // 1/8 per frame
   ```
4. On every frame, it writes `output = input - ref`.

The map is `calloc`ed on every connect, and the tests look at the *uncorrected* frame.  A camera
that heats unevenly adds its own gradient to every frame, so after a warm restart no scene passes
and the map stays empty.  Measured on the Seek Compact above, pointed at a uniform surface:

| | value | limit |
|---|---|---|
| detail (`max_range`, feature 30101) | 99 | 50 |
| step (`scaled_gradient`, feature 30103) | 4037 | 2048 |

Neither the app nor the library ever sets the force flag.  The app talks to libseekip only through
the feature enum in `SeekwareNativeLib`, which has no such ID.  In the 2.3.4 disassembly, the
immediate 30105 appears only in `gradient_setfeature`.

The shutter does not help either.  The shutter frame (frame type 1, the temperature stage's FF0)
measures the sensor's own offsets.  The shutter usually sits between the lens and the sensor, so
infrared from a warm lens or housing in front of it is not in that frame.

| feature | field | default |
|---|---|---|
| 30100 | `grad_p0` (detail limit) | factory `gradient_peak_threshold`, else 50 (206-px core; 70 on the 1401 core); feature 900 sets it to 80 again every frame for "W-" models of device types 4 and 24 |
| 30102 | `grad_p1` (step limit, Q8) | factory `gradient_cell_threshold` × 256, else 2048 |
| 30105 | `enable`: force | 0 |
| 30101 / 30103 | last `max_range` / `scaled_gradient` | read only |
| 30104 | update count: frames that changed the map | read only |

## The patch

- **The button.**  `seekpatch.Flat.attach(activity)` runs right after the camera activity's
  `setContentView`.  The activity is the one whose `onCreate` also looks up the `SurfaceView`.
  The helper finds the top bar by its resource name, `main_view_top_panel`, present in every
  release 1.9.1 – 2.3.4.  It adds the button on the bar's right, so the settings page and the other
  panels that cover the bar cover the button too.  Patches decode with `apktool d -r`, which
  leaves the resources untouched; the button is built in code.
- **The camera thread.**  `seekpatch.Flat.frame(handle)` runs right after the per-frame
  feature-900 call (the hook `smoothing_settings` uses), before the frame is processed.  On a tap:
  1. It logs the current detail and step against their limits (`adb logcat -s seek-thermal-apk-patches`).
  2. It sets 30105 = 1 and remembers the update count, 30104.
  3. Once the count has gone up by 40 (the *Flat field frames* setting, below), it sets
     30105 = 0.  That leaves (7/8)⁴⁰ ≈ 0.5 % of the old map, about 1.5 s at the Compact's ~27 fps.

  It does the same on the second filter's copy of the stage (+ 40000), where Mosaic cores run it;
  on other cameras that copy is idle.  The stock test takes over again afterwards, so the map
  stays as learned.  Feature 900 rewrites the filter mask every frame, but not 30105.
- **Failure cases.**  With no frames within 2 s the toast says *No camera image*.  Five seconds
  without 40 updates (for longer runs, 150 ms a frame plus one second), or a reconnect (a new library handle, whose map starts empty), end the run
  and ask for another tap.  The patch never writes to an old handle.
- `seekpatch.SeekIP`, written by the patch, calls the app's own `seekIPsetFeature` /
  `seekIPgetFeature` wrappers, found by the native each one calls.

The stage's output feeds the temperature readings as well as the picture, as it always has.  After
a tap, readings off-centre lose the camera's gradient too; readings at the centre do not change.

### Setting

*Settings → Image & Video → Flat field frames*: how many frames one tap learns from.  The map moves
1/8 of the way per frame, so N frames learn 1 − (7/8)ᴺ of the gradient:

| frames | 5 | 10 | 15 | 20 | 30 | 40 (default) | 60 |
|---|---|---|---|---|---|---|---|
| learned | 49 % | 74 % | 87 % | 93 % | 98 % | 99.5 % | all |

A short run is quicker and forgives a hand that moves; a second tap goes on from where the first
stopped.  `seekpatch.FlatSettings` sets `Flat.updates`, read when a tap starts.  On the Pixel 5
frames took 0.15 s and 60 frames 1.9 s, each from a fresh map on a warm camera; 60 left visibly less
of the gradient at the edges than 5.

Versions: 2.2.0 – 2.3.4.  The gradient features are verified in libseekip 2.10.5.0 (app 2.2.2) and
2.11.3.2 (2.2.3 – 2.3.4), and the patch refuses older apps, like `smoothing_settings`.  Sources:
[`helpers/java/seekpatch/Flat.java`](../helpers/java/seekpatch/Flat.java),
[`FlatSettings.java`](../helpers/java/seekpatch/FlatSettings.java).

## Other stages that look related

| stage | what it does | why it is not the answer |
|---|---|---|
| `sbnuc` (bit `0x2`, smoothing on) | Pulls each pixel toward its 3 × 3 median, only in locally flat areas, only while the scene moves (> 10 % of flat pixels change by > 14 counts).  Otherwise the map decays by 1/128 per frame. | A smooth gradient has pixel ≈ median, so it cannot see one. |
| `fsc`, flat-scene correction (bit `0x4000`, libseekip 2.11.3.2 = app 2.2.3+; enable 112 / 212, controls 31000–31010 / 71000–71010) | Start (31002) accumulates 10 frames into a per-pixel offset map, which is subtracted from then on.  Seek's SDK 4.4.1 exposes it as `seekcamera_store_flat_scene_correction`: filter 2, gradient correction off, then 71001 + 71002, then it saves the map. | Dormant in the app.  Its default mode (blend 0) stores the offsets with an unsigned conversion (`FCVTZU` in the arm64 build), so negative offsets become 0 and only pixels warmer than the mean are pulled down; blend 1 (71003 = 1) stores them signed.  The map keeps the noise of a 10-frame average.  It is a candidate for a per-pixel mode, which could also take out the left-edge strip. |
| `shutter_cal` (temperature stage, 10200–10210, run gate 409 → bit `0x200`) | The same accumulator, applied to the temperature plane. | Dormant. |
