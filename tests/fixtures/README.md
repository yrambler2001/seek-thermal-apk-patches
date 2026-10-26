# Test fixtures

Synthetic, hand-written smali -- no Seek code.  Each tree reproduces only the *shapes* the patches
look for (the strings, API calls and call sequences named in each patch's docstring), so the
patches can be tested without an APK.

| dir | mimics | how the render thread's handlers reach it |
|---|---|---|
| `lambda/`   | Seek Thermal 2.3.x       | lambda methods of the render thread, `invoke-direct {p0}` |
| `accessor/` | Seek Thermal 2.1 - 2.2   | inner Runnable classes, static synthetic accessors |
| `virtual/`  | Seek Thermal 1.9 - 2.0   | inner classes, package-private methods via `invoke-virtual` |
| `common/`   | all                      | shader program, per-frame features, native lib, logger, the "Save Uncompressed" reader, the video and sound recorders, the encoder thread, the activity with the microphone check (and the d8 outlines it calls) and the live view's layout, the Image & Video settings fragment and another settings fragment, the palette list and the palette preference, the per-frame thermography results and the temperature bar, the USB requests to the camera, the hidden settings' readers, the frame-rate counter, the analytics thread with the uploader it sets up (which uses Apache HTTP), the camera library's USB receiver with its camera, USB holder, USB wrapper and outlined flagged registration |

The photo method (with its EXIF writer and PNG flag) lives in each shape's `Pipeline.smali`; the
render threads of `lambda/` and `accessor/` also hand frames to the video encoder and create / drop
a window surface (`video_quality`, `resume_fix`), which `virtual/` lacks, so those patches refuse it.

`project/` is an `apktool d -r` style project (apktool.yml, binary AndroidManifest.xml -- targetSdk 35,
no `<uses-library>`, no `android:required` -- and resources.arsc) the trees are copied into, so `apktool b` can assemble the patched smali.
`split/AndroidManifest.xml` is the binary manifest of a config split of the same app
(`split="config.arm64_v8a"`); the bundle tests zip it with a native library into a split apk.  The
binary files are generated from `project-src/` by `project-src/build.sh`.
