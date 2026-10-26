# seek-thermal-apk-patches

Unofficial patches for the **Seek Thermal** Android app (`com.tyriansystems.SeekThermal`, 1.9.1 – 2.3.4):
a live view at the camera's full frame rate and as sharp as the iOS app's, a switch for each image
filter, lossless photos, videos as good as the photos, buttons for flat field, colour lock, shutter
and calibration, and fixes for the app's crashes and USB bugs.  Bring your own APK: seek-thermal-apk-patches
patches it on your computer and signs it with your own key.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)

**Contents:** [What you get](#what-you-get) · [Quick start](#quick-start) · [Usage](#usage) ·
[Results](#results) · [Compatibility](#compatibility) · [FAQ](#faq) ·
[Every patch](docs/README.md) · [Changelog](CHANGELOG.md)

<p><img alt="One laptop board in five columns: a colour photo aligned to the thermal ones; stock with the smoothing switch off; stock with it on; seek-thermal-apk-patches at its default settings, the same as on the iOS app; and with Smart smoothing added" src="docs/images/smoothing-photos.avif">
<img alt="Crops of eight spots of the board, the same spot across each row: the colour photo, then stock with the smoothing switch off is blurred, stock with it on is smeared bilinearly, seek-thermal-apk-patches at its default settings keeps each sensor pixel sharp with its grain, as the iOS app does, and with Smart smoothing added it stays sharp with less grain" src="docs/images/smoothing-crops.avif"></p>

<sub>A laptop board: a colour photo, aligned to the thermal frame, and photos saved by each app with a
Seek Compact on a Pixel 8 Pro; the smoothing switch is the stock app's *Image smoothing*, on by default.
Each thermal photo auto-ranges its own colour span, which is why the default-settings one looks paler
around the chip.  Below them, 2× crops of eight spots, the same spot across each row, thermal pixels kept.  The
stock switch's *off* adds a 3×3 blur and *on* smears each sensor pixel bilinearly; the patched
app's default settings keep each pixel sharp, as the iOS app does, and Smart smoothing averages its grain over several frames.  Shiny metal (the
SMDs' end caps, the inductor tops) reads cooler than it is: it emits little heat.</sub>

## What you get

Every patch below is in the default set unless marked opt-in.

### A smoother, sharper live view

<img src="docs/images/image-video-settings.avif" width="240" align="right" alt="Settings, Image &amp; Video: the switches and lists the patches add">

- **Every frame.**  The stock live view redraws only when the phone's *own rear camera* delivers a
  frame, at 15 fps.  Patched, it shows every thermal frame: 32 fps.  (The app's *Show Frame Rate*
  reads about the camera's rate in both: it counts the frames the app processes, not the ones it
  draws.)  [`full_fps`](docs/full-fps.md)
- **Evenly spaced.**  Frames reach the screen a steady 33 ms apart (every 4th 25 ms, at 120 Hz)
  instead of 21 – 39 ms: the screen's top refresh rate instead of 30 Hz, the camera's USB thread
  ahead of the phone camera's, steady pacing.  [`steady_fps`](docs/steady-fps.md)
- **No hidden phone camera.**  The rear camera runs only in Thermal+, which uses it.  In the plain
  view it cost about 1.5 CPU cores and held the screen at 60 Hz.  [`phone_camera`](docs/phone-camera.md)
- **Sharp upscaling.**  Each sensor pixel stays sharp and blends only across its middle half, as in
  the iOS app, instead of being smeared bilinearly across its whole width.  In Settings: *Smooth*
  (stock), *Sharp 1.5* – *8*, *Blocky*.  The crops at the top show it.  [`sharp_scaling`](docs/sharp-scaling.md)
- **A switch per filter.**  The stock app has one *Image smoothing* switch, and its *off* is the
  smoother picture (it adds a 3×3 blur).  Patched, *Settings → Image & Video* has temporal smoothing,
  3×3 spatial smoothing and pattern correction as separate switches, defaulting to the stock
  picture.  [`smoothing_settings`](docs/smoothing-settings.md)
- **Smart smoothing.**  A noise filter of this project's own that follows the camera's motion and
  averages up to 8 frames per pixel: about half the grain on hand-held scenes, no ghosting.  A
  button, off by default.  [`smart_smoothing`](docs/smart-smoothing.md)

<br clear="right">

<p align="center"><img src="docs/images/frame-rate.avif" width="760" alt="A hand-held recording from each app, side by side: the stock one at 15 fps, the seek-thermal-apk-patches one at 32 fps"></p>

<sub>Left: a recording from the stock app, 15 fps, though its corner reads 28.5 Hz.  Right: one from
seek-thermal-apk-patches, 32 fps (Smart smoothing on, flat field applied).  Each plays at its real rate, 2.5 s
in a loop.</sub>

### Buttons on the camera screen

<img src="docs/images/camera-screen.avif" width="220" align="right" alt="The camera screen with the buttons the patches add: Smart smoothing, Flat field, k·x+b, Shutter and Lock range">

- **Flat field.**  Once the camera has warmed unevenly, every picture has a gradient: bright edges,
  a dark middle, even on a uniform wall.  Point at a uniform surface and tap: the gradient is gone
  (7.8 °C across a wall → under 0.6 °C).  [`flat_field`](docs/flat-field.md)
- **Lock range.**  The stock app re-spreads the colours over every frame, so a hot object entering
  the view recolours everything else.  Tap, and each temperature keeps its colour: the button reads
  *Locked 19–28°C*, and the bar keeps those numbers.  Tap again for automatic.  [`lock_range`](docs/lock-range.md)
- **Shutter.**  The camera recalibrates by itself every few seconds (the Compact: every 5 s): a
  click, a 0.44 s freeze, a jump in the picture and the readings.  Tap to stop the automatic
  shutter (the picture then slowly drifts), tap again to start it.  [`shutter`](docs/shutter.md)
- **k·x+b.**  Your own correction of every temperature the app shows and saves, from a reference
  thermometer say: see [Temperature calibration](#temperature-calibration) below.
- **Smart smoothing**, above.

<br clear="right">

| | the fan | then the warm board |
|---|:---:|:---:|
| **automatic** | <img src="docs/images/lock-auto-1.avif" width="200" alt="Automatic range: the fan, 17 to 27 °C"> | <img src="docs/images/lock-auto-2.avif" width="200" alt="Automatic range: the board, 20 to 32 °C; the fan turns dark blue"> |
| **Lock range** | <img src="docs/images/lock-locked-1.avif" width="200" alt="Locked at 19 to 28 °C: the fan"> | <img src="docs/images/lock-locked-2.avif" width="200" alt="Still locked: the fan keeps its colour, the board above 28 °C is white"> |

<sub>Automatic, the scale follows each frame (17–27 °C, then 20–32 °C): the fan turns from purple to
dark blue once the warm board is in view.  Locked at 19–28 °C, the fan keeps its colour, and what is
hotter than 28 °C is white.</sub>

| Flat field: before | after |
|:---:|:---:|
| <img src="docs/images/flat-field-before.avif" width="200" alt="A uniform wall with a warm camera's gradient, 52 to 66 °F"> | <img src="docs/images/flat-field-after.avif" width="200" alt="The same wall after one tap, 65 °F everywhere"> |

### Temperature calibration

<img src="docs/images/calibration.avif" width="300" align="right" alt="The k·x+b dialog: shown = k × measured + b, with k, the gain (1: none), and b, the offset in °C (0: none); Cancel, Reset, Apply">

The stock app's readings are the camera's factory calibration, with emissivity as the only
setting.  If a reference thermometer disagrees, tap **k·x+b** and enter a gain and an offset:
**shown = k × measured + b**.  [`calibration`](docs/calibration.md), 2.2.3 – 2.3.4.

- **Every temperature follows:** the spot, the minimum and maximum and their markers, the
  temperature bar, the radiometric data saved with *Store All Thermal Data*, and the colouring
  modes that work in degrees (Span & Level, the isotherms).
- **The picture does not change:** the automatic colouring spreads the palette over the sensor's
  raw values, and Lock range is not affected.
- **It stays set** across restarts and reconnects, and the button shows it: *1.02x − 0.5°C*.
  *Reset* goes back to k = 1, b = 0.
- **Any unit:** k is the same in °C, °F and K.  b is entered in the app's unit and kept in °C, so
  the correction holds when the unit is switched.

**Finding k and b.**  With the correction reset, measure two surfaces of known temperature far
apart: ice water and hot water in a matt cup, or a reference thermometer's probe on a matt,
high-emissivity surface.  For readings m₁, m₂ of true temperatures t₁, t₂:

```
k = (t₂ − t₁) / (m₂ − m₁)        b = t₁ − k × m₁
```

For example, ice water (0.0 °C) reads 1.2 °C and hot water a kitchen thermometer puts at 60.0 °C
reads 58.1 °C: k = (60.0 − 0.0) / (58.1 − 1.2) = 1.054 and b = 0.0 − 1.054 × 1.2 = −1.27.  With
one reference only, keep k = 1 and set b to the true temperature minus the reading.

<br clear="right">

### Photos and video

- **Lossless photos.**  PNG instead of JPEG with 4:2:0 colour: the app's own hidden *Save
  Uncompressed*, turned on.  [`png_photos`](docs/png-photos.md)
- **The sensor's own pixels.**  With *Also save a 1x PNG* on (off by default), each photo also gets
  the frame at the sensor's resolution, no overlays, as `img_1x_….png`.  [`photo_1x`](docs/photo-1x.md)
- **Videos as good as the photos.**  HEVC 960×1280 at constant quality (~50 dB PSNR) instead of
  H.264 480×640 at 1.5 Mbit/s; every thermal frame instead of 15 fps; clean stereo 48 kHz sound
  instead of mono with a click at every microphone block.  *Video codec* and *Video quality*
  settings.  [`video_quality`](docs/video-quality.md)
- **The microphone only for videos.**  On Android 11+ the stock app asks for it for photos, videos
  and the gallery, drops the tap, and after two denials none of them start.  Patched, only a video
  asks, and then starts by itself.  [`mic_prompt`](docs/mic-prompt.md)

| stock video | seek-thermal-apk-patches video |
|:---:|:---:|
| <img src="docs/images/video-stock.avif" width="380" alt="2x crop of a frame of a stock video"> | <img src="docs/images/video-patched.avif" width="380" alt="2x crop of the same scene in a patched video"> |

<sub>The same spot in a frame of each recording above, enlarged to the same scale, pixels kept.</sub>

### Stock bugs fixed

| in the stock app | patched | |
|---|---|---|
| it crashes (`glError 0x506`) on returning from Android's permission dialog | the live view comes back | [`resume_fix`](docs/resume-fix.md) |
| from 2.2.0, once the camera screen has closed (Back, or from 2.3.0 an unplug in the background), it loses the camera until it is swiped away | the camera comes back | [`reconnect_fix`](docs/reconnect-fix.md) |
| a second *Allow … to access the USB device?* comes up over the live picture and does nothing | one dialog | [`usb_prompt`](docs/usb-prompt.md) |
| opened again soon after it was swiped away, it often starts flat magenta, every pixel at -40 °C, until the camera is unplugged | the picture | [`relaunch_fix`](docs/relaunch-fix.md) |
| 2.1.6 – 2.3.1 on Android 9+: Google Analytics crashes it about 15 s after launch | Analytics never starts; nothing is sent | [`no_analytics`](docs/no-analytics.md) |
| 2.1.6 – 2.3.1 on Android 9+: the account pages and downloads throw `NoClassDefFoundError` | the HTTP library they use is declared, as in 2.3.3 | [`http_legacy`](docs/http-legacy.md) |

### Defaults and extras

- A new install starts in the *Tyrian* palette instead of *Spectra*, and in Celsius everywhere
  (stock: Fahrenheit on a phone set to English (US)).  A palette or unit you pick is kept.
  [`default_palette`](docs/default-palette.md), [`default_unit`](docs/default-unit.md)
- Settings always shows the five switches the stock app hides behind five taps on *About → Image
  Processing Software*: *Show Frame Rate*, *Save Uncompressed*, *Set Simulation Mode* and two
  registration switches.  [`hidden_settings`](docs/hidden-settings.md)
- *Show Frame Rate*'s number updates every 0.5 s instead of every 3 s.  [`fps_readout`](docs/fps-readout.md)
- Opt-in: the SDK's USB and frame-timing log in `adb logcat -s Seekware`
  ([`debug_log`](docs/debug-log.md)).

Nothing else changes: the same app and the same factory calibration (`calibration` corrects the
readings only once you set k and b).  The patches never change the camera's firmware or flash;
the USB requests they add are the firmware's own shutter switch, sent only after the Shutter
button is tapped, which unplugging the camera undoes, and a standard SET_INTERFACE when the app
opens the camera (`relaunch_fix`), which only restarts the USB packet numbering.

## Quick start

From the app downloaded from APKPure to the patched app on your phone, with every suggested patch.
You need a computer with Windows, macOS or Linux.

**1. Download the app.**  On [apkpure.com](https://apkpure.com), search for *Seek Thermal* and
download version **2.3.4**, the newest the patches are tested on.  Either file works, `.xapk` or
`.apk`.  Other sources are under *Getting the APK* below.

**2. Install Java, Python and seek-thermal-apk-patches** (once).  It goes into its own Python virtual
environment, the folder `seek-thermal-apk-patches` in your home folder; deleting that folder removes it.

<details open>
<summary><b>Windows</b> (PowerShell)</summary>

```powershell
winget install Python.Python.3.13
winget install EclipseAdoptium.Temurin.21.JDK
# close PowerShell and open a new window, so it finds Python and Java
py -m venv "$HOME\seek-thermal-apk-patches"
& "$HOME\seek-thermal-apk-patches\Scripts\pip.exe" install https://github.com/yrambler2001/seek-thermal-apk-patches/archive/refs/heads/main.zip
```

</details>

<details>
<summary><b>macOS</b> (Terminal)</summary>

```sh
brew install python openjdk              # Homebrew: https://brew.sh
python3 -m venv ~/seek-thermal-apk-patches
~/seek-thermal-apk-patches/bin/pip install https://github.com/yrambler2001/seek-thermal-apk-patches/archive/refs/heads/main.zip
```

</details>

<details>
<summary><b>Linux</b></summary>

```sh
sudo apt install python3-venv default-jdk-headless        # Debian, Ubuntu, Mint
sudo dnf install python3 java-21-openjdk-headless          # Fedora
sudo pacman -S python jre-openjdk-headless                 # Arch
python3 -m venv ~/seek-thermal-apk-patches
~/seek-thermal-apk-patches/bin/pip install https://github.com/yrambler2001/seek-thermal-apk-patches/archive/refs/heads/main.zip
```

Run only your distribution's line of the first three.

</details>

To update it later, run the same `pip install` line with `--force-reinstall` added.

**Installed as `seek-patch`**, its name before 1.0?  Delete the `seek-patch` folder in your home
folder (the old virtual environment) and follow step 2.  The first run moves your signing key and the
downloaded tools to the new name, so the patched app on your phone still takes updates.

**3. Patch.**  In a new terminal window, put the virtual environment on the path, go to the
download and patch it.  Use your file's name: type `seek-thermal-apk-patches patch ` and drag the file onto the
window.

```sh
source ~/seek-thermal-apk-patches/bin/activate                      # macOS, Linux
seek-thermal-apk-patches doctor                                     # checks Java, fetches the pinned tools, creates your signing key
cd ~/Downloads
seek-thermal-apk-patches patch "Seek Thermal_2.3.4_APKPure.xapk"    # -> Seek Thermal_2.3.4_APKPure-patched-1.0.0.apk
```

```powershell
$env:Path = "$HOME\seek-thermal-apk-patches\Scripts;$env:Path"      # Windows
seek-thermal-apk-patches doctor
cd ~\Downloads
seek-thermal-apk-patches patch "Seek Thermal_2.3.4_APKPure.xapk"
```

The default set adapts to the version: a patch that does not apply to your APK is skipped and named
in the output.  `seek-thermal-apk-patches check FILE` shows the details first.

**4. Install it on the phone.**  The patched app is signed with **your** key, the store app with
Seek's, so Android will not install one over the other.

- **Replace the store app:** uninstall Seek Thermal on the phone (this resets the app's settings;
  saved photos stay), copy the `-patched-….apk` to the phone and open it there.  Android asks once to
  allow installs from the app you opened it with.
- **Keep both:** patch with `--side-by-side` added.  The result installs as a separate app called
  "Seek (patched)".
- **With adb** (USB debugging on): `adb uninstall com.tyriansystems.SeekThermal`, then
  `adb install "Seek Thermal_2.3.4_APKPure-patched-1.0.0.apk"`; or add `--side-by-side --install` to the
  patch command.  adb comes with Android's platform tools: `winget install Google.PlatformTools`,
  `brew install android-platform-tools` or `sudo apt install adb`.

**Getting the APK** – seek-thermal-apk-patches takes one complete ("universal") `.apk`, or a split bundle:
`.xapk` (APKPure), `.apks`, or `.apkm` (APKMirror, unless encrypted).  A bundle is first merged into
one apk with [APKEditor](https://github.com/REAndroid/APKEditor), fetched on first use.  The merged
app has the native code of the ABIs the bundle includes; APKPure's `.xapk` of the Seek app has only
`arm64-v8a`, which every recent phone runs.

To start from the app on your phone, run `adb shell pm path com.tyriansystems.SeekThermal`.  If it
prints a single path, `adb pull` it (drop the `package:` prefix).  If it lists a `base.apk` plus
`split_config.*.apk` files (a split install from the Play Store), pull them all into an empty folder
and zip them into one bundle: `zip seek.apks *.apk`.  The base alone is refused, because its native
code is in a split.  `seek-thermal-apk-patches check FILE` tells you whether a file is usable.

## Usage

```
seek-thermal-apk-patches list                       the patches, their tested versions, the default set
seek-thermal-apk-patches check APP.apk              dry run: which patches apply to this apk, and why not
seek-thermal-apk-patches patch APP.apk [options]    patch, rebuild, align, sign
seek-thermal-apk-patches doctor                     Java, the pinned apktool + uber-apk-signer + APKEditor, your signing key
```

`APP.apk` can also be a split bundle (`.xapk`, `.apks`, `.apkm`); the result is always one `.apk`.

| `patch` option | |
|---|---|
| *(none)* | the default set — every patch but `debug_log` — skipping those that do not apply to this version |
| `-p NAME` | pick patches yourself (repeatable), e.g. `-p full_fps -p debug_log`; each must apply |
| `--all` | every patch, `debug_log` included; each must apply |
| `--side-by-side` | new package name (`<original>.patched`) and label, so it installs next to the store app; `--package`, `--label` to choose them |
| `--install` | `adb install -r` the result |
| `-o FILE`, `-f` | output file (default `<input>-patched-<version>.apk`, with `-side-by-side` before `.apk` for `--side-by-side`), overwrite it |

Upscaling, video codec and video quality are settings in the app (*Settings → Image & Video*).  A
build starts at *Sharp 2* (as iOS), H.265 and QP 18.

`python -m seekpatch` works as well as the `seek-thermal-apk-patches` command.

## Results

Measured on a Pixel 8 Pro (Android 16) with a Seek Compact (firmware 1.3.0.0) — see
[docs/measuring.md](docs/measuring.md) to repeat any of it.

| live view | stock 2.3.4 | patched |
|---|---|---|
| frames from the camera | 32 fps | 32 fps |
| frames on screen | **14.9 fps** (SurfaceFlinger) | **32 fps**: one per camera frame, pausing only for the shutter |
| render-thread CPU | 11 % of a core | 11 % of a core (the scaling runs in the shader) |

| recording | stock 2.3.4 | patched (defaults) |
|---|---|---|
| video | H.264 High, 480×640, 1.5 Mbit/s | HEVC Main (hardware), 960×1280, QP 18: ~9 – 10 Mbit/s on a still scene |
| frame rate | 15.0 fps | 32 fps: every thermal frame, pausing only for the shutter |
| quality vs a near-lossless recording | – | 51.6 dB PSNR, SSIM 0.992, 99.6 % of the sensor noise kept |
| sound | AAC mono 44.1 kHz, 64 kbit/s | AAC stereo 48 kHz, 250 kbit/s |
| photo | JPEG q100, 4:2:0 | PNG, plus a 156×206 PNG of the sensor frame |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/kernel-dark.svg">
  <img alt="Measured upscaling kernels: Android stock is a straight bilinear ramp; iOS and patched Android hold each pixel and blend over the middle half." src="docs/images/kernel-light.svg">
</picture>

How much of the next pixel each display pixel shows, by position — measured from live-view
screenshots (Android) and a saved photo (iOS 2.2.8.0, same camera model and firmware).  Stock
Android is a straight bilinear ramp; iOS holds each pixel for the first and last quarter and blends
across the middle half; `sharp_scaling` reproduces that.  The numbers are in
[docs/sharp-scaling.md](docs/sharp-scaling.md).

## Compatibility

Every release from 1.9.1 to 2.3.4 is decoded, patched, rebuilt and signed by the tests.  2.3.4 also
ran on a Pixel 8 Pro (Android 16), with a Seek Compact and a Compact PRO FF, and on a Redmi 4X
(Android 7.1.2).  Older releases get fewer patches: the filter switches and the Flat field button
start at 2.2.0, Lock range, k·x+b and Smart smoothing at 2.2.3, and the default set skips what does
not apply.  `seek-thermal-apk-patches check FILE` shows what applies to yours.

- [docs/README.md](docs/README.md): every patch, its versions, its Android and camera limits, and
  how it works.
- [docs/versions.md](docs/versions.md): every release, patch by patch.

## How it works

The app is decoded to smali with apktool, edited, rebuilt and signed.  The code is obfuscated
differently in every release, so the patches never use class names: they find code by what it
does, and refuse, changing nothing, when it is not where they expect.  Resources and the binary
manifest are carried over byte for byte.  The details, patch by patch, are in
[docs/README.md](docs/README.md#how-each-patch-works).

## FAQ

**Are temperatures affected?**  `full_fps`, `sharp_scaling` and the photo and video patches only
change when and how the image is drawn and saved.  The readings are computed from the filtered
frame, so the filter switches change them: with temporal smoothing off, spot readings fluctuate
frame to frame like the image does; spatial smoothing averages each reading with its neighbours.
At their defaults the readings are the stock app's.  `flat_field` changes readings only when you
tap it, and the centre of the image keeps its value.  `lock_range` changes only the colours.
`smart_smoothing`, when on, makes spot readings steadier, and small changes take 8–12 frames to
settle.  `calibration` applies your correction on top of the factory calibration, only once you set
one.  For per-pixel temperatures, the app's own *Store All Thermal Data* setting saves a
radiometric TIFF with each photo.

**What are temporal and spatial smoothing?**  The two noise filters of the camera's image library.
Temporal smoothing averages each pixel over time: a calm picture, but faint moving warm things
leave trails.  Spatial smoothing averages each pixel with its 3 × 3 neighbours unless it sits on
an edge: less noise in flat areas, and faint detail blurred.  The stock switch's *off* adds the
spatial blur and keeps the temporal one, which is why it looks softer than *on*.  More in
[docs/smoothing-settings.md](docs/smoothing-settings.md#temporal-and-spatial-smoothing).

**Smart smoothing or Seek's smoothing?**  *Smart smoothing on* replaces only the temporal filter;
*Default temporal smoothing* then has no effect.  For the most detail, leave spatial smoothing off
(the default) and turn Smart smoothing on.

**How big are the videos?**  About 68 MB a minute at the default QP on a still scene, more when the
camera moves; QP 20 is ~55 MB, 24 ~30 MB (see [docs/video-quality.md](docs/video-quality.md)).
Pick it in *Settings → Image & Video → Video quality*.  Set *Video codec* there to H.264 if something
you play them on lacks HEVC; it costs ~20 % more.

**Why no 4:4:4 video?**  No encoder on the phone supports it.  At 960×1280, 4:2:0 still stores colour
at three times the Compact sensor's resolution, so no sensor pixel loses its colour.

**Will the app update itself?**  No: the Play Store will not update an app signed with another key.
Patch the new version when there is one.

**Thermal+?**  It works on the Pixel: the phone's camera opens when Thermal+ is turned on and closes
when it is turned off, and its frames reach the live view.  A Thermal+ photo or video has not been
tried on a phone yet.

## Legal

Not affiliated with, endorsed by or supported by Seek Thermal, Inc.  "Seek Thermal" is their
trademark, used here only to say which app this works with.  This repository contains no Seek code
and no APKs: the patches are applied locally, to an APK you supply, for your own use.  Use at your
own risk.

## Contributing

Bug reports and patches are welcome: [CONTRIBUTING.md](CONTRIBUTING.md) has the tests, the build
of the helpers and what a new patch needs.  The tools in `tools/` measure frame rate, upscaling
kernels and the phone's video encoders ([docs/measuring.md](docs/measuring.md)).

## License

[MIT](LICENSE).  apktool, uber-apk-signer and APKEditor (Apache-2.0) are downloaded on first use, not
bundled.
