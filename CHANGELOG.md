# Changelog

## Unreleased

- Split bundles as input: `.xapk`, `.apks`, `.apkm`, or any zip of a base apk and its splits (such
  as the files `adb pull` gives for a Play Store install).  They are merged into one apk with
  APKEditor 1.4.9 (fetched on first use, verified by sha256), then patched as before.  This covers
  2.3.1, which APKPure only offers as an `.xapk`.
- `smart_smoothing`: a *Smart smoothing* button at the top left of the camera screen, off by
  default and remembered across restarts.  On, the image library's first filter runs without its
  temporal smoothing (`alpf`), and its output goes through seek-patch's motion-compensated noise
  filter, in place.  The filter follows the camera's motion, averages up to 8 frames per pixel,
  removes column stripes and levels the strip at the screen's left edge; temperatures, photos and
  video get the cleaner frame.  It is a small native library of seek-patch's own
  (`helpers/native`, built reproducibly with `helpers/build_native.py`, committed for arm64-v8a and
  armeabi-v7a) that swaps libseekip's GOT entries for `filter_process` / `filter_process_shutter`,
  after checking the library is one of the four builds it was verified on (2.2.3 – 2.3.4).
- Patches can add native libraries (`SmaliTree.add_native_library`): written to `lib/<abi>/` on
  save, rolled back with the patch, stored uncompressed and page aligned in the apk.
- `mic_prompt`: 2.3.1 – 2.3.4.  2.3.1, now testable, has 2.3.3's microphone check.

## 0.2.0 — 2026-10-23

Photos, videos, the microphone and a flat-field button.  All new patches are in the default set.

- `png_photos`: photos as lossless PNG — the app's hidden *Save Uncompressed* setting, forced on
  (Android 11+; 2.1.2 – 2.3.4).
- `photo_1x`: with every photo, the thermal frame at the sensor's resolution as a PNG in
  `Pictures/Seek Thermal 1x/` (2.1.1 – 2.3.4).
- `video_quality`: HEVC (or H.264, `--video-codec avc`) at the photo's 960×1280, constant QP
  (`--video-qp`, default 18, chosen by measurement), one frame per thermal frame instead of 15 fps,
  keyframes every second, BT.709 tags; stereo 48 kHz AAC at 256 kbit/s (2.1.2 – 2.3.4).
- `mic_prompt`: only starting a video asks for the microphone, and the video starts once answered;
  photos and the gallery no longer need it; a settings / record-without-sound dialog once Android
  stops asking (2.3.3 – 2.3.4).
- `flat_field`: a *Flat field* button in the top bar.  Point at a uniform surface and tap; the
  image library's gradient stage learns the camera's own gradient from the next 40 frames, which it
  otherwise does only from frames that already look flat — never on an unevenly warmed camera
  (2.2.0 – 2.3.4).
- `resume_fix`: the app no longer crashes when it comes back from Android's permission dialog — the
  live view's EGL surface is destroyed on pause (1.9.1 – 2.3.4).
- Java helpers (`helpers/java`) compiled to committed smali by `helpers/build.py` (`--check`: is the
  committed smali up to date).
- `tools/codecs.py`: list the phone's encoders, and score a QP ladder against a reference recording.

## 0.1.0 — 2026-10-23

First release.

- `full_fps`: draw every thermal frame instead of every phone-camera frame (1.9.1 – 2.3.4).
- `sharp_scaling`: iOS-like upscaling in the thermal shader, with the same kernel for saved photos
  (2.0 – 2.3.4).
- `no_smoothing`: the "Image smoothing" switch's off position turns temporal and spatial smoothing
  off (2.2.0 – 2.3.4).
- `debug_log`: the SDK's frame-timing log in logcat (2.0 – 2.3.4).
- `seek-patch list / check / patch / doctor`; `--side-by-side`, `--sharpness`, `--install`.  The default
  patch set skips patches that do not apply to the APK's version; `check` suggests the command line.
- Refuses the base APK of a split install (native code missing) instead of building an app that crashes.
- apktool 3.0.3 and uber-apk-signer 1.3.0 fetched on first use and verified by sha256; zipalign in
  Python (16 KiB page alignment for native libraries); a per-user signing key.
