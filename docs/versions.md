# Versions

Every release below was decoded, checked, patched with all applicable patches, rebuilt, aligned and
signed by `tests/test_real_apks.py`.  2.3.4 was also run on a phone (Pixel 8 Pro, Android 16):
live view, photos, video recording, the microphone prompt and the Flat field button.

| app | versionCode | `full_fps` | `sharp_scaling` | `no_smoothing` | `png_photos` | `photo_1x` | `video_quality` | `resume_fix` | `mic_prompt` | `flat_field` | `debug_log` |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1.9.1 | 103 | ✓ | – ¹ | – | – | – | – | ✓ | – ⁴ | – | – ² |
| 1.9.2 | 104 | ✓ | – ¹ | – | – | – | – | ✓ | – ⁴ | – | – ² |
| 1.9.3 | 106 | ✓ | – ¹ | – | – | – | – | ✓ | – ⁴ | – | – ² |
| 1.9.4 | 108 | ✓ | – ¹ | – | – | – | – | ✓ | – ⁴ | – | – ² |
| 1.9.5 | 109 | ✓ | – ¹ | – | – | – | – | ✓ | – ⁴ | – | – ² |
| 2.0 | 156 | ✓ | ✓ | – ³ | – | – | – | ✓ | – ⁴ | – ³ | ✓ |
| 2.0.1 | 158 | ✓ | ✓ | – ³ | – | – | – | ✓ | – ⁴ | – ³ | ✓ |
| 2.0.3 | 160 | ✓ | ✓ | – ³ | – | – | – | ✓ | – ⁴ | – ³ | ✓ |
| 2.1.1 | 162 | ✓ | ✓ | – ³ | – | ✓ | – | ✓ | – ⁴ | – ³ | ✓ |
| 2.1.2 | 180 | ✓ | ✓ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | ✓ |
| 2.1.4 | 210 | ✓ | ✓ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | ✓ |
| 2.1.5 | 217 | ✓ | ✓ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | ✓ |
| 2.1.6 | 240 | ✓ | ✓ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | ✓ |
| 2.1.7 | 250 | ✓ | ✓ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | ✓ |
| 2.2.0 | 260 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ |
| 2.2.1 | 265 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ |
| 2.2.2 | 272 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ |
| 2.2.3 | 276 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ |
| 2.3.0 | 285 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ |
| 2.3.3 | 293 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.4 | 294 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

1. 1.9.x saves photos with a different code path; the live-view part would work, but the patch is
   all or nothing.
2. 1.9.x has no frame-timing log to switch on.
3. The image library these versions ship handles feature 900 differently (2.1.6 / 2.1.7) or is not
   there at all (2.1.5 and older have no `libseekip.so`).  `no_smoothing` and `flat_field` are
   verified on the libraries of 2.2.0 and later and refuse these.
4. Before 2.3.3 the app asks for the microphone together with storage and never blocks a photo or
   video on it, so there is nothing for the patch to change.

`png_photos`, `photo_1x` and `video_quality` start at 2.1.1 / 2.1.2, where the photo and recording
code they hook first appears in this shape; `resume_fix` matches the same pause code in every
release.  2.3.3 was checked and built from the per-ABI APKs (`arm64-v8a`, `armeabi-v7a`).

Regenerate against your own folder of APKs:

```sh
SEEK_APK_DIR=~/apks pytest tests/test_real_apks.py -v              # check only
SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py -v # and build each one
```
