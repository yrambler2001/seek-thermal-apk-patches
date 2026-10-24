# `smart_smoothing` — motion-compensated noise reduction

**Stock:** the app's temporal smoothing (`alpf`) blends a pixel with its previous value only when
the two barely differ.  On a hand-held camera almost every pixel moves a little between frames, so
it either does almost nothing or leaves trails.
**Patched:** a **Smart smoothing** button at the top left of the camera screen.  When it is on, the
image library runs without `alpf`.  Instead, seek-patch's own filter follows the camera's motion
and averages up to eight frames for each pixel.  It also removes most of the column stripes and
levels the bright strip at the screen's left edge.

The button reads *Smart smoothing off* or *Smart smoothing on*.  It is **off** by default, and the
app remembers your choice across restarts.  Off is the stock app: the filter's library is not even
loaded until you first turn it on.  A long press explains what it does.

## What it does to the picture

These numbers come from 11 bursts recorded on a Seek Compact (206 × 156) and replayed offline
through the same filter code.  Each burst is compared with a low-noise reference: a least-squares
merge of all its frames, aligned back onto each frame.  The values are RMS errors in counts, from
frame 16 onwards (lower is better).

- *noise*: the high-pass part of the error, which is the frame-to-frame grain;
- *error*: the whole difference from the reference;
- *edges p99*: the 99th percentile on edges, which shows ghosting and blur.

| burst | noise: raw / stock `alpf` / smart | error: raw / `alpf` / smart | edges p99: raw / `alpf` / smart |
|---|---|---|---|
| keyboard | 6.07 / 5.18 / **2.04** | 6.12 / 5.28 / **4.14** | 17.0 / 17.9 / **14.2** |
| window | 6.88 / 5.98 / **2.84** | 6.41 / 5.51 / **4.91** | 53.3 / 53.2 / **51.4** |
| face, steady | 6.03 / 5.12 / **2.70** | 6.55 / 5.80 / **4.68** | 27.2 / 27.4 / **24.0** |
| face, moving | 7.33 / 6.68 / **4.73** | 8.23 / 7.67 / **7.34** | 71.2 / 71.1 / **67.3** |
| face, moving | 6.06 / 5.16 / **2.89** | 6.48 / 5.65 / **4.78** | 30.9 / 31.3 / **29.1** |
| building | 9.20 / 8.57 / **6.48** | 9.25 / 8.62 / **8.22** | 63.6 / 63.5 / **62.1** |
| hair | 6.34 / 5.51 / **2.97** | 9.30 / 8.68 / **7.32** | 26.2 / 26.4 / **21.5** |
| hair | 6.96 / 6.28 / **4.33** | 8.67 / 8.11 / **7.00** | 29.6 / 29.7 / **24.0** |
| chandelier | 6.63 / 5.65 / **3.38** | 10.63 / 10.05 / **9.19** | 57.0 / 57.2 / 61.5 (worse) |
| phone lying still | 6.90 / 5.99 / **5.09** | 5.60 / 4.40 / **2.79** | 15.5 / 14.0 / **10.0** |
| blank wall | 6.32 / 5.29 / **4.43** | 5.64 / 4.45 / **3.21** | 16.3 / 15.2 / **12.9** |

- The grain falls to 40–75 % of the stock value on hand-held scenes, and to about half on most.
- Faces show no ghosting.  The only scene whose edges get worse is the chandelier, with its thin
  hot lines (+8 % at p99).
- A step of 4σ or more shows at once.  A step of 0.5–2σ reaches 90 % after 8–12 frames.  A scene
  cut restarts the filter on the cut frame.
- The column-stripe part of the fixed pattern drops by 20–40 % (window 2.30 → 1.82 counts, building
  4.32 → 2.62).  The strip at the screen's left edge drops from +64 to +26 counts on the building
  burst.

Everything after the first filter gets the cleaner frame: temperatures, the spot meter, the
contrast stretch, photos and video.

The measurements and the prototype come from seek-patch's research notes: a Python prototype, then
this C code, checked against the prototype on the bursts.

## How it works

The filter is [`helpers/native/tnr.c`](../helpers/native/tnr.c), written from scratch for seek-patch.
It uses only libc and libm, with NEON on arm64.  For each frame it:

1. **Aligns** the frame to the running estimate: a frame-wide shift plus a level offset
   (Gauss-Newton with Huber weights, on a two-level pyramid).  It then refines the shift per 16 px
   tile, with a 0.1 px prior and a 1.5 px limit.
2. **Warps** the estimate into the new frame (Catmull-Rom), together with its per-pixel weight.
3. **Blends** each pixel as `(w·estimate + frame)/(w + 1)`, with `w` capped at 7.  A pixel whose
   residual exceeds 3σ (σ from the noise, plus 0.05 px of misalignment on edges) gets less weight.
   At 6σ, which is motion the alignment missed, it takes the new frame.  The test also runs on the
   3 × 3 mean residual.
4. **Re-estimates the noise** from flat, settled pixels.
5. **Lines and edge:** removes per-frame column and row offsets.  It uses only flat pixels where
   both halves of each line agree (`lines = 3`).  It also levels the last 6 buffer columns, which
   are the screen's left edge (`edge = 6`).
6. **Restarts** when under half the pixels fit, or when the shift exceeds 20 px.

### The hook

The image library, libseekip, does all of its processing in `seekip_process`.  Each image frame
goes through its first filter (`filter_process(filter1, {in, out, scratch, aux, flags})`).  The
temperatures are computed from that output, and then the second filter reads the same buffer.

`lib/<abi>/libseekpatch_smooth.so` swaps libseekip's GOT entries for `filter_process` and
`filter_process_shutter` for its own wrappers.  It finds them through the `R_*_JUMP_SLOT`
relocations in libseekip's dynamic section.  The library is linked `BIND_NOW` with RELRO, so each
slot is made writable for the swap and read-only again afterwards.

- **The first filter.**  The wrapper learns which filter state is the first one: it is the call
  whose output the next call reads as its input.  That is learnt on the first frame, and learnt
  again whenever an unknown state appears, such as a new camera connection.
- **Image frames.**  For frames that are not images, libseekip clears the stages `0x187` before the
  call.  The wrapper treats a frame as an image only if one of those bits is set.  Any other frame
  goes through untouched and restarts the filter.
- **While on:** the wrapper clears `alpf` (bit `0x4`) in the first filter's flags, calls the
  original, and runs the filter in place on its 16-bit output.
- **Shutter:** at the library's shutter restart, the estimate keeps half its weight.  On the bursts,
  halving beat both alternatives.  A reset brings the full noise back at every click.  Keeping the
  whole estimate is the slowest to take up the shutter's new offsets.  A gap of over a second between frames, from an
  unplugged camera or a paused app, restarts the filter.
- **Safety checks:** the hook changes nothing, and logs why, unless all of these hold:
  - exactly one `libseekip.so` is loaded;
  - it binds the PLT now;
  - both GOT slots point at libseekip's own definitions;
  - the sizes of `filter_process`, `filter_process_shutter` and `seekip_process` match one of the
    four builds the frame layout was read from (below).

  The filter runs only on known sizes (206 × 156, 320 × 240) and only on 2-byte pixels.

On the Java side, `seekpatch.Smooth.attach` adds the button to the top bar (`main_view_top_panel`).
It goes on the left; *Flat field* is on the right.  `seekpatch.Smooth.frame()` runs on the camera
thread right after the per-frame feature-900 call.  The first time the button is on, it loads the
library and installs the hook.  After that it passes the switch on.  If the hook refuses, a toast
says *Smart smoothing is not available here*, and `adb logcat -s seek-patch` says why.

The patch adds the library to `lib/arm64-v8a/` and `lib/armeabi-v7a/`, wherever the apk has a
`libseekip.so` for that ABI.  It goes in uncompressed and 16 KiB aligned, because the app maps its
libraries straight out of the apk.  The libraries are built reproducibly by
[`helpers/build_native.py`](../helpers/build_native.py) (NDK r25b, `--check`) and committed, so
patching needs no NDK.

## Measured in the app

Seek Compact on a Pixel 8 Pro, app 2.3.4 side by side, with every default patch:

| | value |
|---|---|
| filter cost on the camera thread | 4.4–5.2 ms thread CPU per frame (wall 5.0–6.0 ms), mostly on the A715 / X3 cores |
| frames on screen, off / on | 25.4 / 24.9 fps; 24.3 / 25.1 fps in a second pair of runs (`tools/fps.sh`, 10–15 s) |
| shutter clicks | 3–6 per 256 frames while the camera warms; each halves the estimate, no hiccup |
| choice across a restart | kept |
| app sent home and reopened, filter on | the app reopens the camera on a new thread; the hook found the new filters again and restarted on the pause; no crash |

Standalone, on one A715 core, the same code took 1.3 ms per frame, or 1.8 ms with the stripe
correction.  The in-app figure is higher: the camera thread shares the cores with the rest of the
app and runs at whatever clock the governor picks (not measured further).  It fits easily in the
Compact's 33 ms frame.

`adb logcat -s seek-patch` prints a line every 256 frames: CPU per frame, the noise estimate,
shutter and other restarts, and the cores it ran on.

## Limits

- **Versions 2.2.3 – 2.3.4** (libseekip 2.11.3.2).  From 2.2.3 on, libseekip calls both functions
  through its PLT.  The libraries of 2.2.0 – 2.2.2 (2.10.5.0) call them directly and export
  neither, so there is nothing to hook, and the patch refuses those versions.  The frame layout was
  read from each verified build:
  - arm64-v8a of 2.2.3 / 2.3.0 (the same code);
  - arm64-v8a of 2.3.1 / 2.3.3 / 2.3.4;
  - armeabi-v7a of 2.2.3 / 2.3.0;
  - armeabi-v7a of 2.3.3 / 2.3.4.

  A future library with a different build turns the hook off at run time.
- **Tested on arm64 only.**  The armeabi-v7a library is built and checked against the 32-bit
  layout, but it has not run on a phone (the Pixel 8 Pro has no 32-bit support).  On armv7 the
  filter uses its portable C code, which is slower than the NEON path.
- **x86 / x86_64** (in the 2.2.x – 2.3.0 apks): no library.  The button then shows the toast.
- **Not yet tested:** a Compact Pro (320 × 240), Thermal+ mode, and unplugging the camera while the
  filter is on.  A 1 s gap restarts the filter, and a new connection is learnt again.
- **Strip and stripes:** `edge` assumes the scene is smooth over the 10 columns at the border.  On
  the blank wall and on one face burst, column w-3 moved from −7 to −19 counts against the
  reference, though the reference itself is unreliable at those columns.  Thin hot lines (the
  chandelier) get slightly worse edges.
- While the filter is on, the image library's own Cube recording holds the filtered frame.
