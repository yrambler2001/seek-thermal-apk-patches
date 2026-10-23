# seek-patch

Unofficial patches for the **Seek Thermal** Android app (`com.tyriansystems.SeekThermal`, 1.9.1 – 2.3.4).
Bring your own APK; get a live view that runs at the camera's real frame rate and is upscaled like
the iOS app, and an "Image smoothing" switch that does what it says.

[![CI](https://github.com/yrambler2001/seek-thermal-apk-patches/actions/workflows/ci.yml/badge.svg)](https://github.com/yrambler2001/seek-thermal-apk-patches/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)

| Image smoothing **off** (stock) | Image smoothing **on** (stock) | Image smoothing **on** + seek-patch |
|:---:|:---:|:---:|
| ![Live view, smoothing off, stock](docs/images/smoothing-off.jpg) | ![Live view, smoothing on, stock](docs/images/smoothing-on.jpg) | ![Live view, smoothing on, patched](docs/images/smoothing-on-patched.jpg) |
| ![2x crop, smoothing off, stock](docs/images/smoothing-off-detail.png) | ![2x crop, smoothing on, stock](docs/images/smoothing-on-detail.png) | ![2x crop, smoothing on, patched](docs/images/smoothing-on-patched-detail.png) |

<sub>Live view of the Seek Thermal app 2.3.4 on a Pixel 8 Pro, a Seek Compact looking at itself in a
mirror, Iron palette; bottom row: 2× crops with the screen pixels kept.  Each shot auto-ranges
its own colour span.</sub>

## What it fixes

| | stock app | with seek-patch | patch |
|---|---|---|---|
| **Frame rate** | **15 fps** on screen: the live view redraws only when the phone's *own rear camera* delivers a frame, and the app runs that camera at 15 fps | **~28 fps**, every thermal frame (the Compact sends ~30) | `full_fps` |
| **Upscaling** | plain bilinear: each sensor pixel is smeared across its whole width | iOS-style: each pixel stays sharp, blending only across the middle half | `sharp_scaling` |
| **"Image smoothing" switch** | *off* is the smoother picture: it adds a 3×3 blur, and the temporal smoothing stays on either way | *off* turns temporal and spatial smoothing off | `no_smoothing` |
| **Diagnostics** | the SDK's USB / frame-timing log is compiled out | `adb logcat -s Seekware` | `debug_log` (opt-in) |

Nothing else changes: the same app and the same calibration.  The patches never touch USB or the
camera firmware.

## Quick start

You need Python 3.9+, a Java runtime (JDK 11 or newer) and, to install from the computer, `adb`.

```sh
pipx install git+https://github.com/yrambler2001/seek-thermal-apk-patches      # or: pip install .  from a checkout
seek-patch doctor                                         # checks Java, fetches the pinned tools
seek-patch patch Seek+Thermal_2.3.4.apk                   # -> Seek+Thermal_2.3.4-patched.apk
```

The default set adapts to the version: a patch that does not apply to your APK is skipped and named
in the output.  `seek-patch check APK` shows the details first.

The patched app is signed with **your** key (created on first run), the store app with Seek's, so
Android will not install one over the other.  Either replace it:

```sh
adb uninstall com.tyriansystems.SeekThermal               # resets the app's settings; saved photos stay
adb install Seek+Thermal_2.3.4-patched.apk
```

or keep both, with the patched one as a separate app called "Seek (patched)":

```sh
seek-patch patch Seek+Thermal_2.3.4.apk --side-by-side --install
```

**Getting the APK** – seek-patch needs one complete ("universal") `.apk` that contains the app's
native libraries.  Installs from the Play Store are usually *split*: `adb shell pm path
com.tyriansystems.SeekThermal` then lists a `base.apk` plus `split_config.*.apk` files, and the base
alone is refused (its native code is in a split).  If `pm path` prints a single path, `adb pull` it
(drop the `package:` prefix).  Otherwise use a universal APK of the release you want; split bundles
(`.xapk`, `.apks`) are not supported yet.  `seek-patch check FILE` tells you whether a file is usable.

## Usage

```
seek-patch list                         the patches, their tested versions, the default set
seek-patch check APP.apk                dry run: which patches apply to this apk, and why not
seek-patch patch APP.apk [options]      patch, rebuild, align, sign
seek-patch doctor                       Java, the pinned apktool + uber-apk-signer, your signing key
```

| `patch` option | |
|---|---|
| *(none)* | the default set: `full_fps`, `sharp_scaling`, `no_smoothing` — those that apply to this version |
| `-p NAME` | pick patches yourself (repeatable), e.g. `-p full_fps -p debug_log`; each must apply |
| `--all` | every patch, `debug_log` included; each must apply |
| `--sharpness N` | `sharp_scaling`'s blend width, 1/N of a pixel: `2` = iOS (default), `3`–`4` crisper, larger approaches visible pixels |
| `--side-by-side` | new package name (`<original>.patched`) and label, so it installs next to the store app; `--package`, `--label` to choose them |
| `--install` | `adb install -r` the result |
| `-o FILE`, `-f` | output file (default `<input>-patched.apk`), overwrite it |

`python -m seekpatch` works as well as the `seek-patch` command.

## Results

Measured on a Pixel 8 Pro (Android 16) with a Seek Compact (firmware 1.3.0.0) — see
[docs/measuring.md](docs/measuring.md) to repeat any of it.

| | stock 2.3.4 | patched |
|---|---|---|
| frames from the camera | ~30 fps | ~30 fps |
| frames on screen (SurfaceFlinger) | **14.9 fps** | **27.5 fps** (the rest: shutter frames, and the panel dropping to 30 Hz) |
| render-thread CPU | 11 % of a core | 11 % of a core (the scaling runs in the shader) |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/kernel-dark.svg">
  <img alt="Measured upscaling kernels: Android stock is a straight bilinear ramp; iOS and patched Android hold each pixel and blend over the middle half." src="docs/images/kernel-light.svg">
</picture>

How much of the next pixel each display pixel shows, by position — measured from live-view
screenshots (Android) and a saved photo (iOS 2.2.8.0, same camera model and firmware).  Stock
Android is a straight bilinear ramp; iOS holds each pixel for the first and last quarter and blends
across the middle half; `sharp_scaling` reproduces that.  The numbers are in
[docs/sharp-scaling.md](docs/sharp-scaling.md).

## Supported versions

Every release listed in [docs/versions.md](docs/versions.md) (1.9.1 – 2.3.4) was decoded,
patched, rebuilt and signed in testing; 2.3.4 was also run on a phone (Pixel 8 Pro).

| patch | versions | |
|---|---|---|
| `full_fps` | 1.9.1 – 2.3.4 | |
| `sharp_scaling` | 2.0 – 2.3.4 | 1.9.x saves photos differently |
| `no_smoothing` | 2.2.0 – 2.3.4 | the feature ids are verified in the image library these versions ship; it refuses older ones |
| `debug_log` | 2.0 – 2.3.4 | 1.9.x has no frame-timing log |

`seek-patch check` tells you for your file, and suggests the command to use.

## How it works

The app is decoded to smali with apktool, edited, rebuilt and signed.  The code is obfuscated
differently in every release, so the patches never use class names: they find code by what it does —
the GL thread that names itself `ThermalPlusRenderThread`, the method that uploads a `ByteBuffer`
with `glTexImage2D`, the shader that samples `thermalTexture` — and refuse, changing nothing, when
the shape is not what they expect.

- [`full_fps`](docs/full-fps.md) — moves the redraw from the phone-camera callback to the thermal upload.
- [`sharp_scaling`](docs/sharp-scaling.md) — a "sharp bilinear" remap in the thermal fragment shader; photos get the same kernel on the CPU.
- [`no_smoothing`](docs/smoothing-switch.md) — after the app sends the smoothing preset, clears the temporal and spatial filter stages when the switch is off.
- [`debug_log`](docs/debug-log.md) — gives the SDK's stripped log methods a body.

By default only the code is decoded (`apktool -r`): resources and the binary manifest are carried
over byte for byte, so a rebuild cannot break them.  `--side-by-side` decodes resources too, to rename
the package.

## FAQ

**Are temperatures affected?**  `full_fps` and `sharp_scaling` only change when and how the image is
drawn.  `no_smoothing` turns off the library's temporal and spatial filters, and the temperature
readout is computed from the filtered frame — so with the switch off, spot readings fluctuate frame
to frame like the image does, instead of being averaged.  The calibration is untouched.

**Will the app update itself?**  No: the Play Store will not update an app signed with another key.
Patch the new version when there is one.

**Thermal+ / video recording?**  Not tested on a phone yet.  By design both keep working:
`full_fps` leaves the phone-camera callback in place (it still feeds Thermal+ and the video
encoder), so recordings keep that camera's 15 fps clock.

**Which GPUs?**  The shader is plain OpenGL ES 2.0, written for any Android GPU; it has been run on
the Pixel 8 Pro's Mali.  GPUs without high-precision fragment shaders (old Mali-400 / 450, early
Tegra) keep the stock bilinear scaling instead of showing artifacts.

## Legal

Not affiliated with, endorsed by or supported by Seek Thermal, Inc.  "Seek Thermal" is their
trademark, used here only to say which app this works with.  This repository contains no Seek code
and no APKs: the patches are applied locally, to an APK you supply, for your own use.  Use at your
own risk.

## Development

```sh
pip install -e '.[dev]'
pytest                     # unit tests on synthetic smali (tests/fixtures), no APK needed
SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py    # against your own apks
```

Adding a patch: [docs/writing-patches.md](docs/writing-patches.md).  The tools in `tools/` measure
frame rate and upscaling kernels ([docs/measuring.md](docs/measuring.md)).

## License

[MIT](LICENSE).  apktool and uber-apk-signer (Apache-2.0) are downloaded on first use, not bundled.
