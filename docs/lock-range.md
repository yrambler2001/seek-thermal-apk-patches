# `lock_range` — a button that keeps the colors where they are

**Stock:** the colors are re-spread over every frame.  Point the camera at a cup of tea and the
rest of the room goes dark; the same wall changes color as warmer or colder things enter and leave
the view.  Two pictures of the same surface, taken a minute apart, can't be compared by color.
**Patched:** a **Lock range** button floats below the top bar, on the right.  Tap it and the image
stays exactly as it is: from then on each temperature keeps the color it had at the tap.  The
button reads, for example, *Locked 14–19°C*, and the temperature bar keeps the two numbers it showed
at the tap.  Anything hotter than the hottest part of the scene at the tap takes the palette's top
color, anything colder its bottom color.  Tap again to go back to automatic.

- **Nothing jumps at the tap or the untap.**  The lock keeps the app's own coloring, curve and all;
  it only stops the app from rebuilding it.  Unlocking hands back to the automatic curve, which
  follows the scene again from that frame.
- **What it applies to:** the live view, photos and videos, which all come from the same colored
  frame, in every display mode.  It lasts until the app is closed.  A camera reconnect unlocks
  (the toast says so): the new connection has no curve to hold.
- **What it doesn't change:** temperatures.  The spot readout, the minimum and maximum, and the
  radiometric data of *Store All Thermal Data* are computed before the coloring.
- **A slow drift:** the curve the app builds is from the sensor's raw values to colors, and the
  lock holds that.  The raw value of a surface shifts a little with each shutter calibration and as
  the camera warms (most in the first minute after connecting), and the colors shift with it.  On a
  flat, low-contrast scene, where a few degrees span the whole palette, that shows; on a scene with
  some contrast it hardly does.  Tap twice to lock afresh.

A long press explains the button.

## How it works

The image library (libseekip) colors each frame in two steps: its contrast stage turns the frame's
16-bit raw values into an 8-bit image, and the colorizer maps that through the palette.  The
contrast stage the app uses (`bclahe_process`, the library's default; the app never picks another)
does, on every frame:

1. a histogram of the raw values in the central 84 % of the frame;
2. clips it (CLAHE-style: bins above a limit give their excess to the rest);
3. averages it with the previous frames' histograms;
4. `create_transfer`: turns the averaged histogram into the curve, one 8-bit level per histogram
   bin, with the ends trimmed by a small percentage;
5. maps every pixel through the curve (interpolating within a bin).

Step 4 makes the colors follow the scene.  The patch's native library, `libseekpatch_lock.so`,
points libseekip's PLT slot for `create_transfer` at a small wrapper.  While locked, the wrapper
returns without calling it for the stage that was locked, so step 5 keeps using the last curve
built: the curve of the frame on screen at the tap.  Steps 1 – 3 still run, so the moment the lock
ends the automatic curve is up to date.  A call for a different stage (a reconnect creates a new
one, whose curve was never built) is passed on and ends the lock.

The temperature bar writes the scene's minimum and maximum next to the palette, from each frame's
results.  While locked it writes the values from the tap instead (the extremes smoothed over the
last few frames, as they are single pixels).

The patch adds:

| where | what |
|---|---|
| `lib/<abi>/libseekpatch_lock.so` | the wrapper and the hook; before changing anything it checks that the slot holds libseekip's own `create_transfer`, of a size seen in a verified build |
| the camera screen, after `setContentView` | `seekpatch.Lock.attach`: the button, in the frame layout that holds the top bar, just after it (so the palette picker and the overlays still cover it) |
| right after the per-frame feature-900 call | `Lock.frame()`: loads and hooks on the first tap, then passes taps on, and hears of a reconnect |
| the method each frame's results arrive in, `(IIIIFFF)V` | `Lock.scene(min, max)`: the scene's minimum and maximum (°C) |
| the temperature bar | its `if (span) { min = span_min; max = span_max; }` labels: `Lock.bar` makes the test true while locked, `Lock.low` / `Lock.high` hand it the values from the tap |

The Java side is found by shape: the feature-900 call (shared with the other patches), the results
method's signature, and the bar's `Canvas` / `Rect` signature with its one span test.

## Versions

2.2.3 – 2.3.4: libseekip 2.11.3.2 calls `create_transfer` through its PLT; 2.2.0 – 2.2.2's
library (2.10.5.0) calls it directly, so there is nothing to hook.  The hook knows the
`create_transfer` of arm64-v8a (2.2.3 – 2.3.4) and armeabi-v7a (2.2.3 – 2.3.0, 2.3.3 – 2.3.4); on
any other library it changes nothing and the button says it is not available.  Built for arm64-v8a
and armeabi-v7a only.

Run on a phone with 2.3.4 arm64 (Pixel 8 Pro, Seek Compact, Iron palette, °C, Smart smoothing on),
pointed at a still, nearly uniform scene, a minute after connecting.  Screenshots 0.4 s before and
after the tap differ by 2.9 and 3.9 (mean absolute difference per color channel, 0 – 255, over the
image), as much as two automatic frames a second apart (2.9); the first version of this patch,
which switched to a linear temperature scale, changed it by 20.  Two seconds later the locked image
had moved by 10 – 18: the scene read about 0.1 °C a second warmer (the bar's 14.3 – 20.2 °C at one
tap, 15.1 – 21.1 °C eight seconds later), the drift described above, which a 6 °C span makes
plain.  armeabi-v7a, a reconnect while locked, and Fahrenheit / Kelvin have not been run on a phone.

Sources: [`helpers/native/lock.c`](../helpers/native/lock.c) (the PLT code it shares with
`smart_smoothing` is in [`plt.c`](../helpers/native/plt.c)),
[`helpers/java/seekpatch/Lock.java`](../helpers/java/seekpatch/Lock.java).
