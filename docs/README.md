# Patches

Every patch, in the order seek-thermal-apk-patches applies them.  *✓* marks the default set
(`seek-thermal-apk-patches patch APP.apk`); add an opt-in one with `-p NAME`.  *Versions* are the app releases
it was tested on; [versions.md](versions.md) has the release-by-release table and why a patch skips a
release.  Each name links to its page: what the stock app does, what changes, how it was measured.

<!-- patches: written by tools/patch_index.py from the patch modules, do not edit -->
| patch | what it does | versions | default |
|---|---|---|:---:|
| [`full_fps`](full-fps.md) | draw every thermal frame instead of every phone-camera frame: live view 15 → ~30 fps | 1.9.1 – 2.3.4 | ✓ |
| [`steady_fps`](steady-fps.md) | steady, evenly spaced live view: the screen's top refresh rate, camera threads first, frame pacing | 1.9.1 – 2.3.4 | ✓ |
| [`default_palette`](default-palette.md) | the camera starts in the Tyrian palette instead of Spectra, until another is picked | 2.0 – 2.3.4 | ✓ |
| [`default_unit`](default-unit.md) | a new install shows Celsius, also on a phone set to English (US), until another unit is picked | 1.9.1 – 2.3.4 | ✓ |
| [`sharp_scaling`](sharp-scaling.md) | iOS-like upscaling: blend over half a pixel instead of a whole one (GPU shader) | 2.0 – 2.3.4 | ✓ |
| [`smoothing_settings`](smoothing-settings.md) | Settings switches for Seek's temporal / spatial smoothing and pattern correction, and Smart smoothing | 2.2.0 – 2.3.4 | ✓ |
| [`png_photos`](png-photos.md) | save photos as lossless PNG (the app's hidden "Save Uncompressed" setting, forced on) | 2.1.2 – 2.3.4 | ✓ |
| [`hidden_settings`](hidden-settings.md) | Settings always shows the app's hidden switches (Show Frame Rate, Save Uncompressed, ...) | 1.9.3 – 2.3.4 | ✓ |
| [`fps_readout`](fps-readout.md) | the "Show Frame Rate" readout (Hz) updates every 0.5 s instead of every 3 s | 2.0 – 2.3.4 | ✓ |
| [`photo_1x`](photo-1x.md) | a setting to save each photo's thermal frame at the sensor's resolution too (PNG, img_1x_... next to it) | 2.1.1 – 2.3.4 | ✓ |
| [`video_quality`](video-quality.md) | video at the photo's size, HEVC constant quality, every thermal frame (no 15 fps cap), 48 kHz stereo | 2.1.2 – 2.3.4 | ✓ |
| [`phone_camera`](phone-camera.md) | the phone's rear camera runs only in Thermal+: no hidden preview in the plain view, up to 120 Hz | 2.1.2 – 2.3.4 | ✓ |
| [`resume_fix`](resume-fix.md) | no crash on returning from a dialog (permission prompt) over the live view | 1.9.1 – 2.3.4 | ✓ |
| [`reconnect_fix`](reconnect-fix.md) | the camera comes back after the camera screen closed (Back, or unplugging it in the background) | 1.9.1 – 2.3.4 | ✓ |
| [`usb_prompt`](usb-prompt.md) | one USB permission dialog for the camera, not a second one that does nothing | 1.9.1 – 2.3.4 | ✓ |
| [`relaunch_fix`](relaunch-fix.md) | the camera starts with a picture after the app was swiped away or killed, not a -40 °C magenta screen | 1.9.1 – 2.3.4 | ✓ |
| [`no_analytics`](no-analytics.md) | Google Analytics never starts: nothing is sent (2.1.6 – 2.3.1 no longer crash 15 s after launch) | 1.9.1 – 2.3.4 | ✓ |
| [`http_legacy`](http-legacy.md) | declare Android's Apache HTTP library: 2.1.6 – 2.3.1 use it undeclared and crash with it on Android 9+ | 2.1.6 – 2.3.1 | ✓ |
| [`mic_prompt`](mic-prompt.md) | ask for the microphone when a video starts; photos and the gallery never need it | 2.3.1 – 2.3.4 | ✓ |
| [`flat_field`](flat-field.md) | a "Flat field" button: point at a uniform surface, tap, and the camera's own gradient is removed | 2.2.0 – 2.3.4 | ✓ |
| [`lock_range`](lock-range.md) | a "Lock range" button: the colors stay as they are, whatever enters the view | 2.2.3 – 2.3.4 | ✓ |
| [`shutter`](shutter.md) | a "Shutter" button: stop the camera's automatic shutter (no clicks, no frozen frames), and start it again | 1.9.1 – 2.3.4 | ✓ |
| [`calibration`](calibration.md) | a "k·x+b" button: your own linear correction of every temperature the app shows and saves | 2.2.3 – 2.3.4 | ✓ |
| [`smart_smoothing`](smart-smoothing.md) | a "Smart smoothing" button: a motion-compensated noise filter instead of the app's temporal smoothing | 2.2.3 – 2.3.4 | ✓ |
| [`debug_log`](debug-log.md) | send the SDK's compiled-out debug log (USB timing, DAQ fps) to logcat, tag "Seekware" | 2.0 – 2.3.4 | opt-in |
<!-- /patches -->

## Android and camera

Beyond the app version:

- `steady_fps` — asking for the screen's top refresh rate needs Android 11+.
- `png_photos` — Android 11+: older Android cannot write EXIF into a PNG, so the app keeps its
  JPEG setting there.
- `mic_prompt` — the stock prompts it fixes are Android 11+ behaviour.
- `no_analytics`, `http_legacy` — the crashes they fix happen on Android 9+.
- `usb_prompt` — the second dialog was seen on Android 7.1.2 (Redmi 4X).
- `relaunch_fix` — the stuck start was seen with a Compact PRO FF; the Compact is untested.
- `shutter` — the command is the camera firmware's, read in the Compact's 1.3.0.0; a camera that
  refuses it gets a message.
- `lock_range`, `calibration`, `smart_smoothing` — native hooks for arm64-v8a and armeabi-v7a (not
  x86 / x86_64); only arm64-v8a has run on a phone.
- `sharp_scaling` — any OpenGL ES 2.0 GPU; GPUs without high-precision fragment shaders (old
  Mali-400 / 450, early Tegra) keep the stock scaling.

## How each patch works

The app is decoded to smali with apktool, edited, rebuilt and signed.  The code is obfuscated
differently in every release, so the patches never use class names: they find code by what it does —
the GL thread that names itself `ThermalPlusRenderThread`, the method that uploads a `ByteBuffer`
with `glTexImage2D`, the shader that samples `thermalTexture` — and refuse, changing nothing, when
the shape is not what they expect.

- [`full_fps`](full-fps.md) — moves the redraw from the phone-camera callback to the thermal upload.
- [`steady_fps`](steady-fps.md) — has the live view's window ask for the screen's top rate, runs the camera library's USB thread and frame loop at nice −19 (its USB thread is a `HandlerThread`, which drops the library's priority) and the render thread at −10, and sets each frame's presentation time to its arrival plus a steady delay.
- [`default_palette`](default-palette.md) — changes the default of the app's `color_palette` preference from Spectra's index to Tyrian's, read from the app's palette list.
- [`default_unit`](default-unit.md) — has every read of the app's `default_unit` integer resource, which the `units` preference defaults to, answer 1 (Celsius).
- [`sharp_scaling`](sharp-scaling.md) — a "sharp bilinear" remap in the thermal fragment shader; photos get the same kernel on the CPU.  Its settings set the shader's sharpness, 1 being the stock sample.
- [`smoothing_settings`](smoothing-settings.md) — adds the switches to the app's own settings screen; after the app sends the smoothing preset, makes the *on* preset the base and sets the temporal, spatial and pattern-correction stages from the switches.
- [`png_photos`](png-photos.md) — turns on the app's hidden *Save Uncompressed* setting.
- [`hidden_settings`](hidden-settings.md) — has the readers of the switches' "allowed" preferences, which the settings screen checks before removing each switch, return true.
- [`fps_readout`](fps-readout.md) — changes the frame counter's 3000 ms window to 500 ms.
- [`photo_1x`](photo-1x.md) — keeps the photo method's sensor-sized frame and writes it once the photo is saved, when the *Also save a 1x PNG* setting is on.
- [`video_quality`](video-quality.md) — picks and configures the encoder, hands it every thermal frame, records 48 kHz stereo, copies each microphone block from its first byte and stamps the sound by its samples.  How the QP was chosen is in there; the settings pick the codec and the QP or a bitrate per recording.
- [`phone_camera`](phone-camera.md) — takes the phone camera's opening out of the live view's start and opens / closes it from the stream's Thermal+ switch; the front / back switch waits for it.
- [`resume_fix`](resume-fix.md) — destroys the live view's EGL surface before the app drops it on pause.
- [`reconnect_fix`](reconnect-fix.md) — from 2.2.0 empties the camera library's `unRegisterUSBIntent()`, so its USB receiver stays registered, and from 2.3.0 closes and releases a camera the last camera screen left open when the next one registers, and drops the `finish()` in `MainActivity.onRestart()` that closed the screen when it came back without a camera; the permission request is addressed to the app itself and, on Android 13+, the receiver is not exported, so another Seek app's answers do not reach it.
- [`usb_prompt`](usb-prompt.md) — routes the camera library's permission requests through a small helper that skips one while the same camera's dialog waits for its answer; the library's receiver ends the wait.
- [`relaunch_fix`](relaunch-fix.md) — has the camera library set the camera's USB interface again right after claiming it, which resets both ends' data toggles: the first packet of the first frame is no longer dropped as a repeat.
- [`no_analytics`](no-analytics.md) — replaces the run loop of the bundled Google Analytics thread: the SDK is disabled before it creates its connection, store and uploader, and what the app queues is dropped.
- [`http_legacy`](http-legacy.md) — adds `<uses-library android:name="org.apache.http.legacy" android:required="false"/>` to the binary manifest (or to the text one with `--side-by-side`).
- [`mic_prompt`](mic-prompt.md) — routes the app's microphone check and request through a small helper, and starts the video once the camera runs again.
- [`flat_field`](flat-field.md) — adds the button; a tap has the library's gradient stage learn its correction map from the next 40 frames (the *Flat field frames* setting: 5 – 60), which it otherwise does only for frames that already look flat.
- [`lock_range`](lock-range.md) — adds the button and a second small native library: while locked it keeps the image library's contrast stage from rebuilding its curve (raw value → palette entry) each frame, and the temperature bar keeps the numbers from the tap.
- [`shutter`](shutter.md) — adds the button; a tap sends the camera firmware's request that suspends (or resumes) its automatic shutter, on the app's own connection, just before a frame request.
- [`calibration`](calibration.md) — adds the button and a small native library that hooks the image library's thermography stage, where each frame is turned into degrees, and maps its outputs (the per-pixel temperatures, the spot, the minimum and maximum) through *k × t + b*.
- [`smart_smoothing`](smart-smoothing.md) — adds the button and a small native library of seek-thermal-apk-patches' own: it hooks the image library's first filter, which then runs without its temporal smoothing, and filters its output in place.
- [`debug_log`](debug-log.md) (opt-in) — gives the SDK's stripped log methods a body.

Patches that need more than a few instructions add helper classes written in Java
([`helpers/java`](../helpers/java)) and compiled to smali, which is committed: patching needs no
Android SDK.  The native libraries of `smart_smoothing`, `lock_range` and `calibration`
([`helpers/native`](../helpers/native)) are committed too, built reproducibly with the NDK.  By
default only the code is decoded (`apktool -r`): resources and the binary manifest are carried over
byte for byte, so a rebuild cannot break them.  The one exception is `http_legacy`, which adds one
element to the binary manifest and leaves every other chunk as it was.  `--side-by-side` decodes
resources too, to rename the package.  A split bundle is merged into one apk first, by APKEditor,
which also drops the manifest attributes that make Android require the splits.

## Other pages

- [versions.md](versions.md) — every release, every patch, and installing an older release past Play Protect.
- [measuring.md](measuring.md) — how the frame rates, upscaling kernels and encoders were measured.
- [writing-patches.md](writing-patches.md) — adding a patch.
