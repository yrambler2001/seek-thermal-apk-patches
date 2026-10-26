# seek-patch

Unofficial patches for the **Seek Thermal** Android app (`com.tyriansystems.SeekThermal`, 1.9.1 – 2.3.4).
Bring your own APK; get a live view that runs at the camera's real frame rate and is upscaled like
the iOS app, a switch for each of the image filters, lossless photos with the sensor's
own pixels beside them, videos as good as the photos, and a button that flattens the gradient of a
warm camera.

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
| **Smoothness** | the screen runs the live view at 30 Hz, so about two frames a second are dropped and the one before stays up twice as long; the camera's USB thread waits behind the phone camera's threads and about one frame a second is never fetched; frames reach the screen 21 – 39 ms apart | every frame the camera sends is shown, a steady delay after it arrived: 33 ms apart, every 4th 25 ms (120 Hz, with `phone_camera`; at 60 Hz every 7th or 8th 17 ms), and a third as many frames lost | `steady_fps` |
| **Phone camera** | the phone's own rear camera runs with the live view, also in the plain thermal view, where nothing uses it: about 1.5 CPU cores on a Pixel 8 Pro, and Android holds the screen at 60 Hz for an app with a camera open | it runs only in Thermal+; the plain view gets the screen's top rate | `phone_camera` |
| **Palette** | a new install starts in *Spectra* | starts in *Tyrian* (a palette you pick is kept, as before) | `default_palette` |
| **Unit** | a new install shows Fahrenheit on a phone set to English (US), Celsius elsewhere | Celsius everywhere (a unit you pick is kept, as before) | `default_unit` |
| **Upscaling** | plain bilinear: each sensor pixel is smeared across its whole width | iOS-style: each pixel stays sharp, blending only across the middle half; in Settings, *Smooth* (stock), *Sharp 1.5* – *8* or *Blocky* | `sharp_scaling` |
| **Smoothing switches** | one "Image smoothing" switch, and *off* is the smoother picture: it adds a 3×3 blur, and the temporal smoothing stays on either way | in *Settings → Image & Video*, a switch per filter: temporal smoothing, 3×3 spatial smoothing, pattern correction, and Smart smoothing with its two options; the defaults are the stock picture | `smoothing_settings` (or, opt-in, `no_smoothing`: the old switch's *off* turns both smoothings off) |
| **Photos** | JPEG, quality 100 but 4:2:0 colour; the PNG setting is hidden | lossless PNG (the app's own *Save Uncompressed*, turned on) | `png_photos` |
| **Hidden settings** | five switches in Settings appear only after tapping *About → Image Processing Software* five times | always there: *Show Frame Rate*, *Save Uncompressed*, *Set Simulation Mode* and two registration switches | `hidden_settings` |
| **Frame-rate readout** | *Show Frame Rate*'s number in the live view changes every 3 s | every 0.5 s | `fps_readout` |
| **Sensor pixels** | only the 1280×960 upscaled photo | with *Also save a 1x PNG* on in Settings (off by default), also the frame at the sensor's resolution, PNG, no overlays, next to the photo as `img_1x_….png` | `photo_1x` |
| **Video** | H.264 480×640 at a fixed 1.5 Mbit/s, **15 fps** (the phone camera's clock), mono 44.1 kHz 64 kbit/s sound with a click at every microphone block (a copying bug), stamped with the times its reads started: uneven with Android 7's encoder (a stutter about three times a second on a Redmi 4X) | HEVC **960×1280** at constant quality (~50 dB PSNR) or a bitrate you pick (*Video codec* and *Video quality* settings), **every thermal frame**, clean stereo 48 kHz 256 kbit/s sound, each frame stamped by its samples | `video_quality` |
| **Microphone** | Android 11+: photos, videos and the gallery all ask for the microphone and drop the tap; after two denials none of them starts again | only starting a video asks, and the video then starts by itself; when Android won't ask again, a dialog offers the settings page or recording without sound | `mic_prompt` |
| **Warm camera** | once the camera has warmed unevenly, every picture has a gradient (bright edges, dark middle), even of a uniform wall | a **Flat field** button: point at a uniform surface, tap, and the gradient is gone (14 °F across a wall → under 1 °F) | `flat_field` |
| **Color range** | the colors are re-spread over every frame: a hot object entering the view recolors everything else, and the same wall changes color from one picture to the next | a **Lock range** button: tap, and the image stays as it is, each temperature keeping its color (the bar keeps its numbers, *Locked 14–19°C*); tap again for automatic | `lock_range` |
| **Shutter** | the camera recalibrates by itself every few seconds (the Compact: every 5 s): a click, a 0.44 s freeze, a jump in the picture and the readings | a **Shutter** button: tap and the automatic shutter is off (no clicks; the picture slowly drifts instead), tap again and it is back | `shutter` |
| **Temperature accuracy** | the factory calibration, with emissivity as the only setting | a **k·x+b** button: enter a gain and an offset (from a reference thermometer, say) and every temperature the app shows and saves is corrected, *shown = k × measured + b* | `calibration` |
| **Noise** | the temporal smoothing blends only pixels that did not change: little effect on a hand-held camera, trails when it does act | a **Smart smoothing** button (off by default; also a switch in Settings): a filter that follows the camera's motion and averages up to 8 frames per pixel, plus stripe and left-edge correction; about half the grain on hand-held scenes, no ghosting on faces | `smart_smoothing` |
| **Returning from a dialog** | the app crashes (`glError 0x506`) after Android's permission dialog | the live view comes back | `resume_fix` |
| **Reconnecting** | from 2.2.0, once the camera screen has closed (Back on the home page, or, from 2.3.0, coming back after unplugging the camera in the background), the app loses the camera until it is swiped away: from 2.3.0 *Connect Your Camera* with the camera plugged in, in 2.2.x a black live view after the next unplug and replug.  From 2.3.0 the tap that brings the app back after an unplug closes it, and the permission dialog comes up over the home screen | the camera comes back, in the screen the tap brought back | `reconnect_fix` |
| **USB permission** | after the camera is plugged in, the app asks twice: a second *Allow … to access the USB device?* comes up over the live picture and does nothing | one dialog | `usb_prompt` |
| **Reopening** | opened again soon after it was swiped away or force-stopped, the app often starts with a flat magenta picture: every pixel and the spot at -40 °C, until the camera is unplugged (a USB packet lost: the first frame's header) | the picture | `relaunch_fix` |
| **Analytics** | up to 2.3.1, Google Analytics runs while *Send Usage Data* is on (the default), and on Android 9+ it crashes 2.1.6 – 2.3.1 about 15 s after launch | never starts: nothing is sent, no crash | `no_analytics` |
| **Apache HTTP** | on Android 9+, 2.1.6 – 2.3.1 lack the HTTP library they use (they do not declare it): Analytics, the account pages and downloads throw `NoClassDefFoundError` | declared in the manifest, as in 2.3.3: Android loads it | `http_legacy` |
| **Diagnostics** | the SDK's USB / frame-timing log is compiled out | `adb logcat -s Seekware` | `debug_log` (opt-in) |

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

**2. Install Java, Python and seek-patch** (once).  seek-patch goes into its own Python virtual
environment, the folder `seek-patch` in your home folder; deleting that folder removes it.

<details open>
<summary><b>Windows</b> (PowerShell)</summary>

```powershell
winget install Python.Python.3.13
winget install EclipseAdoptium.Temurin.21.JDK
# close PowerShell and open a new window, so it finds Python and Java
py -m venv "$HOME\seek-patch"
& "$HOME\seek-patch\Scripts\pip.exe" install https://github.com/yrambler2001/seek-thermal-apk-patches/archive/refs/heads/main.zip
```

</details>

<details>
<summary><b>macOS</b> (Terminal)</summary>

```sh
brew install python openjdk              # Homebrew: https://brew.sh
python3 -m venv ~/seek-patch
~/seek-patch/bin/pip install https://github.com/yrambler2001/seek-thermal-apk-patches/archive/refs/heads/main.zip
```

</details>

<details>
<summary><b>Linux</b></summary>

```sh
sudo apt install python3-venv default-jdk-headless        # Debian, Ubuntu, Mint
sudo dnf install python3 java-21-openjdk-headless          # Fedora
sudo pacman -S python jre-openjdk-headless                 # Arch
python3 -m venv ~/seek-patch
~/seek-patch/bin/pip install https://github.com/yrambler2001/seek-thermal-apk-patches/archive/refs/heads/main.zip
```

Run only your distribution's line of the first three.

</details>

To update seek-patch later, run the same `pip install` line with `--force-reinstall` added.

**3. Patch.**  In a new terminal window, put the virtual environment on the path, go to the
download and patch it.  Use your file's name: type `seek-patch patch ` and drag the file onto the
window.

```sh
source ~/seek-patch/bin/activate                      # macOS, Linux
seek-patch doctor                                     # checks Java, fetches the pinned tools, creates your signing key
cd ~/Downloads
seek-patch patch "Seek Thermal_2.3.4_APKPure.xapk"    # -> Seek Thermal_2.3.4_APKPure-patched.apk
```

```powershell
$env:Path = "$HOME\seek-patch\Scripts;$env:Path"      # Windows
seek-patch doctor
cd ~\Downloads
seek-patch patch "Seek Thermal_2.3.4_APKPure.xapk"
```

The default set adapts to the version: a patch that does not apply to your APK is skipped and named
in the output.  `seek-patch check FILE` shows the details first.

**4. Install it on the phone.**  The patched app is signed with **your** key, the store app with
Seek's, so Android will not install one over the other.

- **Replace the store app:** uninstall Seek Thermal on the phone (this resets the app's settings;
  saved photos stay), copy the `-patched.apk` to the phone and open it there.  Android asks once to
  allow installs from the app you opened it with.
- **Keep both:** patch with `--side-by-side` added.  The result installs as a separate app called
  "Seek (patched)".
- **With adb** (USB debugging on): `adb uninstall com.tyriansystems.SeekThermal`, then
  `adb install "Seek Thermal_2.3.4_APKPure-patched.apk"`; or add `--side-by-side --install` to the
  patch command.  adb comes with Android's platform tools: `winget install Google.PlatformTools`,
  `brew install android-platform-tools` or `sudo apt install adb`.

**Getting the APK** – seek-patch takes one complete ("universal") `.apk`, or a split bundle:
`.xapk` (APKPure), `.apks`, or `.apkm` (APKMirror, unless encrypted).  A bundle is first merged into
one apk with [APKEditor](https://github.com/REAndroid/APKEditor), fetched on first use.  The merged
app has the native code of the ABIs the bundle includes; APKPure's `.xapk` of the Seek app has only
`arm64-v8a`, which every recent phone runs.

To start from the app on your phone, run `adb shell pm path com.tyriansystems.SeekThermal`.  If it
prints a single path, `adb pull` it (drop the `package:` prefix).  If it lists a `base.apk` plus
`split_config.*.apk` files (a split install from the Play Store), pull them all into an empty folder
and zip them into one bundle: `zip seek.apks *.apk`.  The base alone is refused, because its native
code is in a split.  `seek-patch check FILE` tells you whether a file is usable.

## Usage

```
seek-patch list                         the patches, their tested versions, the default set
seek-patch check APP.apk                dry run: which patches apply to this apk, and why not
seek-patch patch APP.apk [options]      patch, rebuild, align, sign
seek-patch doctor                       Java, the pinned apktool + uber-apk-signer + APKEditor, your signing key
```

`APP.apk` can also be a split bundle (`.xapk`, `.apks`, `.apkm`); the result is always one `.apk`.

| `patch` option | |
|---|---|
| *(none)* | the default set — every patch but `debug_log` and `no_smoothing` — skipping those that do not apply to this version |
| `-p NAME` | pick patches yourself (repeatable), e.g. `-p full_fps -p debug_log`; each must apply |
| `--all` | every patch, `debug_log` included, but not `no_smoothing` (the alternative to `smoothing_settings`); each must apply |
| `--sharpness N` | `sharp_scaling`'s blend width, 1/N of a pixel: `2` = iOS (default), `3`–`4` crisper, larger approaches visible pixels.  The default entry of the *Upscaling* setting |
| `--video-codec hevc\|avc` | `video_quality`'s codec: HEVC (default; H.264 is the automatic fallback) or H.264 first, for players without HEVC |
| `--video-qp N` | `video_quality`'s constant quantizer, 10 – 40: lower is better and bigger; `18` (default) ≈ 68 MB/min on a still scene.  The default of the *Video quality* setting |
| `--side-by-side` | new package name (`<original>.patched`) and label, so it installs next to the store app; `--package`, `--label` to choose them |
| `--install` | `adb install -r` the result |
| `-o FILE`, `-f` | output file (default `<input>-patched.apk`), overwrite it |

`python -m seekpatch` works as well as the `seek-patch` command.

## Results

Measured on a Pixel 8 Pro (Android 16) with a Seek Compact (firmware 1.3.0.0) — see
[docs/measuring.md](docs/measuring.md) to repeat any of it.

| live view | stock 2.3.4 | patched |
|---|---|---|
| frames from the camera | ~30 fps | ~30 fps |
| frames on screen (SurfaceFlinger) | **14.9 fps** | **27.5 fps** (the rest: shutter frames, and the panel dropping to 30 Hz) |
| render-thread CPU | 11 % of a core | 11 % of a core (the scaling runs in the shader) |

| recording | stock 2.3.4 | patched (defaults) |
|---|---|---|
| video | H.264 High, 480×640, 1.5 Mbit/s | HEVC Main (hardware), 960×1280, QP 18: ~9 – 10 Mbit/s on a still scene |
| frame rate | 15.0 fps | 24.6 – 27.7 fps: every thermal frame, pausing only for the shutter |
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

## Supported versions

Every release listed in [docs/versions.md](docs/versions.md) (1.9.1 – 2.3.4) was decoded,
patched, rebuilt and signed in testing; 2.3.4 was also run on a phone (Pixel 8 Pro).

| patch | versions | |
|---|---|---|
| `full_fps` | 1.9.1 – 2.3.4 | |
| `steady_fps` | 1.9.1 – 2.3.4 | the screen rate needs Android 11+ |
| `sharp_scaling` | 2.0 – 2.3.4 | 1.9.x saves photos differently |
| `smoothing_settings` | 2.2.0 – 2.3.4 | the feature ids are verified in the image library these versions ship; it refuses older ones.  The Smart smoothing switches come with `smart_smoothing` |
| `no_smoothing` | 2.2.0 – 2.3.4 | opt-in, the alternative to `smoothing_settings`; same library check |
| `png_photos` | 2.1.2 – 2.3.4 | Android 11+ (older Android cannot write EXIF into a PNG; it keeps the setting) |
| `hidden_settings` | 1.9.3 – 2.3.4 | all five switches from 2.0; 1.9.5 has four, 1.9.3 – 1.9.4 one |
| `fps_readout` | 2.0 – 2.3.4 | 1.9.x has no frame-rate readout |
| `photo_1x` | 2.1.1 – 2.3.4 | |
| `default_palette` | 2.0 – 2.3.4 | |
| `default_unit` | 1.9.1 – 2.3.4 | |
| `video_quality` | 2.1.2 – 2.3.4 | |
| `phone_camera` | 2.1.2 – 2.3.4 | needs `full_fps` and `video_quality`, which starts at 2.1.2 |
| `resume_fix` | 1.9.1 – 2.3.4 | |
| `reconnect_fix` | 1.9.1 – 2.3.4 | the bug is in 2.2.0 – 2.3.4; 1.9.1 – 2.1.7 register the receiver again themselves and only get the part that keeps other Seek apps' permission answers out |
| `usb_prompt` | 1.9.1 – 2.3.4 | the second dialog seen on Android 7.1.2 (Redmi 4X) |
| `relaunch_fix` | 1.9.1 – 2.3.4 | the stuck start seen with a Compact PRO FF; the Compact is untested |
| `no_analytics` | 1.9.1 – 2.3.4 | |
| `http_legacy` | 2.1.6 – 2.3.1 | older releases target API 27 or lower (Android adds the library); 2.3.3 – 2.3.4 declare it |
| `mic_prompt` | 2.3.1 – 2.3.4 | older releases ask for the microphone with storage and never block on it |
| `flat_field` | 2.2.0 – 2.3.4 | the gradient features are verified in the image library these versions ship; it refuses older ones |
| `lock_range` | 2.2.3 – 2.3.4 | arm64-v8a and armeabi-v7a; older image libraries call the contrast curve's builder directly, so there is nothing to hook |
| `shutter` | 1.9.1 – 2.3.4 | the command is the camera firmware's: read in the Compact's 1.3.0.0; a camera that refuses it gets a message |
| `calibration` | 2.2.3 – 2.3.4 | arm64-v8a and armeabi-v7a; older image libraries call the thermography stage directly, so there is nothing to hook |
| `smart_smoothing` | 2.2.3 – 2.3.4 | arm64-v8a and armeabi-v7a; older image libraries call the filter directly, so there is nothing to hook |
| `debug_log` | 2.0 – 2.3.4 | 1.9.x has no frame-timing log |

The settings a patch adds to *Settings → Image & Video* come with it on each of its versions.
`seek-patch check` tells you for your file, and suggests the command to use.

## How it works

The app is decoded to smali with apktool, edited, rebuilt and signed.  The code is obfuscated
differently in every release, so the patches never use class names: they find code by what it does —
the GL thread that names itself `ThermalPlusRenderThread`, the method that uploads a `ByteBuffer`
with `glTexImage2D`, the shader that samples `thermalTexture` — and refuse, changing nothing, when
the shape is not what they expect.  A split bundle is merged into one apk first, by APKEditor, which
also drops the manifest attributes that make Android require the splits.

- [`full_fps`](docs/full-fps.md) — moves the redraw from the phone-camera callback to the thermal upload.
- [`sharp_scaling`](docs/sharp-scaling.md) — a "sharp bilinear" remap in the thermal fragment shader; photos get the same kernel on the CPU.  Its settings set the shader's sharpness, 1 being the stock sample.
- [`smoothing_settings`](docs/smoothing-settings.md) — adds the switches to the app's own settings screen; after the app sends the smoothing preset, makes the *on* preset the base and sets the temporal, spatial and pattern-correction stages from the switches.
- [`no_smoothing`](docs/smoothing-switch.md) (opt-in) — after the app sends the smoothing preset, clears the temporal and spatial filter stages when the switch is off.
- [`steady_fps`](docs/steady-fps.md) — has the live view's window ask for the screen's top rate, runs the camera library's USB thread and frame loop at nice −19 (its USB thread is a `HandlerThread`, which drops the library's priority) and the render thread at −10, and sets each frame's presentation time to its arrival plus a steady delay.
- [`png_photos`](docs/png-photos.md) — turns on the app's hidden *Save Uncompressed* setting.
- [`hidden_settings`](docs/hidden-settings.md) — has the readers of the switches' "allowed" preferences, which the settings screen checks before removing each switch, return true.
- [`fps_readout`](docs/fps-readout.md) — changes the frame counter's 3000 ms window to 500 ms.
- [`default_palette`](docs/default-palette.md) — changes the default of the app's `color_palette` preference from Spectra's index to Tyrian's, read from the app's palette list.
- [`default_unit`](docs/default-unit.md) — has every read of the app's `default_unit` integer resource, which the `units` preference defaults to, answer 1 (Celsius).
- [`photo_1x`](docs/photo-1x.md) — keeps the photo method's sensor-sized frame and writes it once the photo is saved, when the *Also save a 1x PNG* setting is on.
- [`video_quality`](docs/video-quality.md) — picks and configures the encoder, hands it every thermal frame, records 48 kHz stereo, copies each microphone block from its first byte and stamps the sound by its samples.  How the QP was chosen is in there; the settings pick the codec and the QP or a bitrate per recording.
- [`phone_camera`](docs/phone-camera.md) — takes the phone camera's opening out of the live view's start and opens / closes it from the stream's Thermal+ switch; the front / back switch waits for it.
- [`mic_prompt`](docs/mic-prompt.md) — routes the app's microphone check and request through a small helper, and starts the video once the camera runs again.
- [`flat_field`](docs/flat-field.md) — adds the button; a tap has the library's gradient stage learn its correction map from the next 40 frames (the *Flat field frames* setting: 5 – 60), which it otherwise does only for frames that already look flat.
- [`lock_range`](docs/lock-range.md) — adds the button and a second small native library: while locked it keeps the image library's contrast stage from rebuilding its curve (raw value → palette entry) each frame, and the temperature bar keeps the numbers from the tap.
- [`shutter`](docs/shutter.md) — adds the button; a tap sends the camera firmware's request that suspends (or resumes) its automatic shutter, on the app's own connection, just before a frame request.
- [`calibration`](docs/calibration.md) — adds the button and a small native library that hooks the image library's thermography stage, where each frame is turned into degrees, and maps its outputs (the per-pixel temperatures, the spot, the minimum and maximum) through *k × t + b*.
- [`smart_smoothing`](docs/smart-smoothing.md) — adds the button and a small native library of seek-patch's own: it hooks the image library's first filter, which then runs without its temporal smoothing, and filters its output in place.
- [`resume_fix`](docs/resume-fix.md) — destroys the live view's EGL surface before the app drops it on pause.
- [`reconnect_fix`](docs/reconnect-fix.md) — from 2.2.0 empties the camera library's `unRegisterUSBIntent()`, so its USB receiver stays registered, and from 2.3.0 closes and releases a camera the last camera screen left open when the next one registers, and drops the `finish()` in `MainActivity.onRestart()` that closed the screen when it came back without a camera; the permission request is addressed to the app itself and, on Android 13+, the receiver is not exported, so another Seek app's answers do not reach it.
- [`usb_prompt`](docs/usb-prompt.md) — routes the camera library's permission requests through a small helper that skips one while the same camera's dialog waits for its answer; the library's receiver ends the wait.
- [`relaunch_fix`](docs/relaunch-fix.md) — has the camera library set the camera's USB interface again right after claiming it, which resets both ends' data toggles: the first packet of the first frame is no longer dropped as a repeat.
- [`no_analytics`](docs/no-analytics.md) — replaces the run loop of the bundled Google Analytics thread: the SDK is disabled before it creates its connection, store and uploader, and what the app queues is dropped.
- [`http_legacy`](docs/http-legacy.md) — adds `<uses-library android:name="org.apache.http.legacy" android:required="false"/>` to the binary manifest (or to the text one with `--side-by-side`).
- [`debug_log`](docs/debug-log.md) — gives the SDK's stripped log methods a body.

Patches that need more than a few instructions add helper classes written in Java
([`helpers/java`](helpers/java)) and compiled to smali, which is committed: patching needs no Android
SDK.  The native libraries of `smart_smoothing`, `lock_range` and `calibration` ([`helpers/native`](helpers/native)) are committed too, built
reproducibly with the NDK.  By default only the code is decoded (`apktool -r`): resources and the binary manifest are
carried over byte for byte, so a rebuild cannot break them.  The one exception is `http_legacy`, which adds one
element to the binary manifest and leaves every other chunk as it was.  `--side-by-side` decodes
resources too, to rename the package.

## FAQ

**What are temporal and spatial smoothing?**  The two noise filters in the camera's image library
(libseekip).  They run before the colours are applied, so they shape the temperature readings as
well as the picture.

- *Temporal* smoothing (`alpf`) averages each pixel over time.  It compares the pixel with its
  previous output.  A difference *d* below a threshold *T*, set from the camera's factory
  sensitivity, shows only a fraction *d/T* of itself: noise barely gets through, while a change of
  *T* or more shows at once.  The result becomes the history for the next frame, so a small real
  change creeps in over several frames.  The picture is calm, but faint moving warm things leave
  trails and small temperature changes show late.
- *Spatial* smoothing (`aslpf`) averages each pixel with its neighbours, one frame at a time.  Every
  pixel becomes the mean of its 3 × 3 neighbourhood unless strong slopes around it mark an edge.
  Noise in flat areas drops by up to 3×, but detail too faint to count as an edge is blurred: fine
  texture, thin wires.  The edge test compares only the top-right side of a pixel with the
  bottom-left side, so an edge running exactly from bottom-left to top-right is not seen, and it
  is blurred too.

| | temporal | spatial | detail kept |
|---|---|---|---|
| stock, "Image smoothing" on | on | off | 14.1 % |
| stock, "Image smoothing" off | on | **on** | 10.6 % |
| `no_smoothing`, switch off | off | off | 15.3 % |

That is why stock *off* looks softer than *on*: it adds the spatial blur and keeps the temporal
one.  With `smoothing_settings` each has its own switch (*Default temporal smoothing*, *Default
spatial smoothing (3×3)*), beside *Default pattern correction*, which removes the sensor's fixed
pattern.  *Detail kept* is the per-pixel structure left in the sensor frame, measured as in
[docs/smoothing-switch.md](docs/smoothing-switch.md).

**Are temperatures affected?**  `full_fps`, `sharp_scaling` and the photo and video patches only
change when and how the image is drawn and saved.  The temperature readout is computed from the
filtered frame, so the filter switches of `smoothing_settings` (and `no_smoothing`'s *off*) change
it: with temporal smoothing off, spot readings fluctuate frame to frame like the image does, instead
of being averaged; spatial smoothing averages each reading with its neighbours.  At their defaults
the readings are the stock app's.
`flat_field` changes readings only when you tap it: the correction it learns applies to the
temperatures as well as the picture.  The camera's own gradient leaves the readings, and the centre
of the image keeps its value.  `lock_range` changes only the colors: the readings are computed before them.  `smart_smoothing`, when on, filters the frame the temperatures are
computed from: spot readings get steadier (the noise averaged over up to 8 aligned frames instead
of the stock temporal filter), and small changes take 8–12 frames to settle fully.  The factory calibration is untouched;
`calibration` applies your own correction on top of it, to every reading, only once you set one.  For per-pixel temperatures, the app's own *Store All Thermal Data*
setting saves a radiometric TIFF with each photo.

**How big are the videos?**  About 68 MB a minute at the default QP on a still scene, more when the
camera moves; QP 20 is ~55 MB, 24 ~30 MB (see the table in
[docs/video-quality.md](docs/video-quality.md)).  Pick it in *Settings → Image & Video → Video
quality*, or set the default with `--video-qp`.  Choose `--video-codec avc` if something you play
them on lacks HEVC; it costs ~20 % more.

**Why no 4:4:4 video?**  No encoder on the phone supports it.  At 960×1280, 4:2:0 still stores colour
at three times the Compact sensor's resolution, so no sensor pixel loses its colour.

**Will the app update itself?**  No: the Play Store will not update an app signed with another key.
Patch the new version when there is one.

**Smart smoothing or Seek's smoothing?**  *Smart smoothing on* replaces only the temporal filter with
seek-patch's; *Default temporal smoothing* then has no effect.  Spatial smoothing and pattern
correction keep their own switches: for the most detail, leave spatial smoothing off (the default)
and turn Smart smoothing on.  With `no_smoothing` instead of `smoothing_settings`, the 3×3 blur
follows the old switch.

**Thermal+?**  Not tested on a phone yet.  By design it keeps working: the phone-camera callback still
latches the camera image Thermal+ blends in, and the video encoder draws the same scene as the
screen.

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
python3 helpers/build.py   # after changing a Java helper (needs the Android SDK)
python3 helpers/build_native.py   # after changing helpers/native (needs the NDK r25b)
SEEK_SUPERRES=~/superres pytest tests/test_native.py   # the hook against the research stage on a burst
```

Adding a patch: [docs/writing-patches.md](docs/writing-patches.md).  The tools in `tools/` measure
frame rate, upscaling kernels and the phone's video encoders ([docs/measuring.md](docs/measuring.md)).

## License

[MIT](LICENSE).  apktool, uber-apk-signer and APKEditor (Apache-2.0) are downloaded on first use, not
bundled.
