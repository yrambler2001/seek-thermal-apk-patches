# Versions

Every release below was decoded, checked, patched with all applicable patches, rebuilt, aligned and
signed by `tests/test_real_apks.py`.  2.3.4 was also run on a phone (Pixel 8 Pro, Android 16):
live view, photos, video recording, the microphone prompt, the Flat field button, Smart smoothing and
the smoothing switches in Settings.

| app | versionCode | `full_fps` | `sharp_scaling` | `smoothing_settings` | `no_smoothing` | `png_photos` | `photo_1x` | `video_quality` | `resume_fix` | `mic_prompt` | `flat_field` | `smart_smoothing` | `debug_log` |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1.9.1 | 103 | ✓ | – ¹ | – | – | – | – | – | ✓ | – ⁴ | – | – ³ | – ² |
| 1.9.2 | 104 | ✓ | – ¹ | – | – | – | – | – | ✓ | – ⁴ | – | – ³ | – ² |
| 1.9.3 | 106 | ✓ | – ¹ | – | – | – | – | – | ✓ | – ⁴ | – | – ³ | – ² |
| 1.9.4 | 108 | ✓ | – ¹ | – | – | – | – | – | ✓ | – ⁴ | – | – ³ | – ² |
| 1.9.5 | 109 | ✓ | – ¹ | – | – | – | – | – | ✓ | – ⁴ | – | – ³ | – ² |
| 2.0 | 156 | ✓ | ✓ | – ³ | – ³ | – | – | – | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.0.1 | 158 | ✓ | ✓ | – ³ | – ³ | – | – | – | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.0.3 | 160 | ✓ | ✓ | – ³ | – ³ | – | – | – | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.1.1 | 162 | ✓ | ✓ | – ³ | – ³ | – | ✓ | – | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.1.2 | 180 | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.1.4 | 210 | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.1.5 | 217 | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ³ | ✓ |
| 2.1.6 | 240 | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ⁵ | ✓ |
| 2.1.7 | 250 | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ⁵ | ✓ |
| 2.2.0 | 260 | ✓ | ✓ | ✓ ⁶ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | – ⁵ | ✓ |
| 2.2.1 | 265 | ✓ | ✓ | ✓ ⁶ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | – ⁵ | ✓ |
| 2.2.2 | 272 | ✓ | ✓ | ✓ ⁶ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | – ⁵ | ✓ |
| 2.2.3 | 276 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ | ✓ |
| 2.3.0 | 285 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ | ✓ |
| 2.3.1 | 290 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.3 | 293 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.4 | 294 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

1. 1.9.x saves photos with a different code path; the live-view part would work, but the patch is
   all or nothing.
2. 1.9.x has no frame-timing log to switch on.
3. The image library these versions ship handles feature 900 differently (2.1.6 / 2.1.7) or is not
   there at all (2.1.5 and older have no `libseekip.so`).  `smoothing_settings`, `no_smoothing` and
   `flat_field` are verified on the libraries of 2.2.0 and later and refuse these.  (The settings
   screen `smoothing_settings` hooks exists from 2.0 on.)
4. Before 2.3.1 the app asks for the microphone together with storage and never blocks a photo or
   video on it, so there is nothing for the patch to change.
5. `smart_smoothing` hooks the image library's calls of its filter through the PLT, which libseekip
   makes from 2.11.3.2 (app 2.2.3) on; the libraries of 2.1.6 – 2.2.2 call the filter directly.  The hook
   checks at run time that the library is one of the four builds whose frame layout was read
   (arm64-v8a and armeabi-v7a of 2.2.3 / 2.3.0 and of 2.3.1 – 2.3.4).  Only arm64-v8a has run on a
   phone; 2.2.3 and 2.3.0 also ship x86 / x86_64 code, for which there is no library.
6. Seek's three filter switches only: the Smart smoothing switches come with `smart_smoothing`,
   which starts at 2.2.3.

The settings in *Settings → Image & Video* come with their patches wherever those apply: upscaling
(`sharp_scaling`) 2.0 – 2.3.4, video quality (`video_quality`) 2.1.2 – 2.3.4, Seek's filters
(`smoothing_settings`) 2.2.0 – 2.3.4, Smart smoothing 2.2.3 – 2.3.4.  The build test checks each
section class in the built app.  Only 2.3.4 has shown them on a phone.

`no_smoothing` is opt-in, the alternative to `smoothing_settings`: the build test applies every
patch but it, and `check` tests each patch alone.

`png_photos`, `photo_1x` and `video_quality` start at 2.1.1 / 2.1.2, where the photo and recording
code they hook first appears in this shape; `resume_fix` matches the same pause code in every
release.  2.3.1 was checked and built from its `.xapk` split bundle, 2.3.3 from its `.xapk`
and from its per-ABI APKs (`arm64-v8a`, `armeabi-v7a`).

Regenerate against your own folder of APKs:

```sh
SEEK_APK_DIR=~/apks pytest tests/test_real_apks.py -v              # check only
SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py -v # and build each one
```
