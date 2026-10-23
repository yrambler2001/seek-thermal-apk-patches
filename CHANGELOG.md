# Changelog

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
