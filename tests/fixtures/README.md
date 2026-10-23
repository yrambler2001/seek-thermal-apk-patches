# Test fixtures

Synthetic, hand-written smali -- no Seek code.  Each tree reproduces only the *shapes* the patches
look for (the strings, API calls and call sequences named in each patch's docstring), so the
patches can be tested without an APK.

| dir | mimics | how the render thread's handlers reach it |
|---|---|---|
| `lambda/`   | Seek Thermal 2.3.x       | lambda methods of the render thread, `invoke-direct {p0}` |
| `accessor/` | Seek Thermal 2.1 - 2.2   | inner Runnable classes, static synthetic accessors |
| `virtual/`  | Seek Thermal 1.9 - 2.0   | inner classes, package-private methods via `invoke-virtual` |
| `common/`   | all                      | shader program, per-frame features, native lib, logger, the "Save Uncompressed" reader, the video and sound recorders, the encoder thread |

The photo method (with its EXIF writer and PNG flag) lives in each shape's `Pipeline.smali`; the
render threads of `lambda/` and `accessor/` also hand frames to the video encoder and create / drop
a window surface (`video_quality`, `resume_fix`), which `virtual/` lacks, so those patches refuse it.

`project/` is an `apktool d -r` style project (apktool.yml, binary AndroidManifest.xml and
resources.arsc) the trees are copied into, so `apktool b` can assemble the patched smali.  The
binary files are generated from `project-src/` by `project-src/build.sh`.
