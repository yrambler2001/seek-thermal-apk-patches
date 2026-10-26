# Versions

Every release below was decoded, checked, patched with all applicable patches, rebuilt, aligned and
signed by `tests/test_real_apks.py`.  2.3.4 was also run on a phone (Pixel 8 Pro, Android 16):
live view, photos, video recording, the microphone prompt, the Flat field, Lock range, k·x+b and Shutter
buttons, Smart smoothing, the smoothing switches and the hidden switches in Settings, the
frame-rate readout, the steady live view, the phone camera opening and closing with Thermal+, and the camera coming
back after Back.  2.3.4 also ran on a Redmi 4X (Android 7.1.2): the floating buttons in one row,
the settings' summaries, the *Video codec* setting, the *Video quality* bitrates, the sound's
timestamps and clicks, and one USB permission dialog.  `shutter` sends its
command to the camera, so what it does depends on the camera's firmware, not on the app version
(see [shutter.md](shutter.md)).  2.2.2 was run on
the same phone, once with `no_analytics` alone and once with `http_legacy` alone; neither crashes
(see [no-analytics.md](no-analytics.md), [http-legacy.md](http-legacy.md)).

Installing an older release may run into Google Play Protect, which checks apps installed from
outside the Play Store.  It can block them with *"Unsafe app blocked — This app was built for an
older version of Android and doesn't include the latest privacy protections"*.  That refers to the
app's own targetSdkVersion (30 for 2.2.2), which seek-patch does not change.  The stock APK gets the
same treatment, and Play Protect is not consistent: one 2.2.2 build installed, and the next was
blocked.  To install anyway, turn off *Scan apps with Play Protect* in the Play Store's Play
Protect settings for the install, then turn it back on.

| app | versionCode | `full_fps` | `steady_fps` | `default_palette` | `default_unit` | `sharp_scaling` | `smoothing_settings` | `no_smoothing` | `png_photos` | `hidden_settings` | `fps_readout` | `photo_1x` | `video_quality` | `phone_camera` | `resume_fix` | `reconnect_fix` | `usb_prompt` | `no_analytics` | `http_legacy` | `mic_prompt` | `flat_field` | `lock_range` | `shutter` | `calibration` | `smart_smoothing` | `debug_log` |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1.9.1 | 103 | ✓ | ✓ | – ⁷ | ✓ | – ¹ | – | – | – | – ¹⁰ | – ¹¹ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – | – | ✓ | – | – ³ | – ² |
| 1.9.2 | 104 | ✓ | ✓ | – ⁷ | ✓ | – ¹ | – | – | – | – ¹⁰ | – ¹¹ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – | – | ✓ | – | – ³ | – ² |
| 1.9.3 | 106 | ✓ | ✓ | – ⁷ | ✓ | – ¹ | – | – | – | ✓ ¹⁰ | – ¹¹ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – | – | ✓ | – | – ³ | – ² |
| 1.9.4 | 108 | ✓ | ✓ | – ⁷ | ✓ | – ¹ | – | – | – | ✓ ¹⁰ | – ¹¹ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – | – | ✓ | – | – ³ | – ² |
| 1.9.5 | 109 | ✓ | ✓ | – ⁷ | ✓ | – ¹ | – | – | – | ✓ ¹⁰ | – ¹¹ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – | – | ✓ | – | – ³ | – ² |
| 2.0 | 156 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | – | ✓ | ✓ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.0.1 | 158 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | – | ✓ | ✓ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.0.3 | 160 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | – | ✓ | ✓ | – | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.1.1 | 162 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | – | ✓ | ✓ | ✓ | – | – ¹⁶ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.1.2 | 180 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.1.4 | 210 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.1.5 | 217 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁴ | ✓ | ✓ | – ¹² | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ³ | ✓ |
| 2.1.6 | 240 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁴ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ⁵ | ✓ |
| 2.1.7 | 250 | ✓ | ✓ | ✓ | ✓ | ✓ | – ³ | – ³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁴ | ✓ | ✓ | ✓ | – ⁴ | – ³ | – ⁸ | ✓ | – ⁹ | – ⁵ | ✓ |
| 2.2.0 | 260 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ⁶ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁵ | ✓ | ✓ | ✓ | – ⁴ | ✓ | – ⁸ | ✓ | – ⁹ | – ⁵ | ✓ |
| 2.2.1 | 265 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ⁶ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁵ | ✓ | ✓ | ✓ | – ⁴ | ✓ | – ⁸ | ✓ | – ⁹ | – ⁵ | ✓ |
| 2.2.2 | 272 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ⁶ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁵ | ✓ | ✓ | ✓ | – ⁴ | ✓ | – ⁸ | ✓ | – ⁹ | – ⁵ | ✓ |
| 2.2.3 | 276 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ¹⁵ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.0 | 285 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ⁴ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.1 | 290 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.3 | 293 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ¹³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2.3.4 | 294 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – ¹³ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

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
7. 1.9.x builds no palette list with Tyrian in it, so `default_palette` has no index to set.
8. `lock_range` hooks the image library's call of `create_transfer` (its contrast curve) through the
   PLT, which libseekip makes from 2.11.3.2 (app 2.2.3) on, as for `smart_smoothing`; the hook knows
   the arm64-v8a and armeabi-v7a builds of 2.2.3 – 2.3.4.
9. `calibration` hooks the image library's call of `thermography_process` through the PLT, as
   `lock_range` does its contrast curve: from 2.11.3.2 (app 2.2.3) on, the arm64-v8a and
   armeabi-v7a builds of 2.2.3 – 2.3.4.
10. The hidden switches are all five from 2.0 on; 1.9.5 has four (no *Show Frame Rate*), 1.9.3 –
    1.9.4 only *Disable Registration*, 1.9.1 – 1.9.2 none.
11. 1.9.x has no frame-rate readout.
12. These releases target API 27 or lower, so Android adds the Apache HTTP library by itself;
    `http_legacy` refuses them (see [http-legacy.md](http-legacy.md)).
13. 2.3.3 and 2.3.4 declare the library themselves.
14. 1.9.1 – 2.1.7 register the camera library's USB receiver again whenever a camera screen starts,
    so they do not lose the camera; `reconnect_fix` only makes the receiver hear its own app (see
    [reconnect-fix.md](reconnect-fix.md)).
15. In 2.2.x the camera manager keeps its camera for the next screen: `reconnect_fix` keeps the
    receiver registered, and there is no camera to release.
16. `phone_camera` needs `video_quality` (without it recordings take the phone camera's frames),
    which starts at 2.1.2; the code it changes has the same shape back to 1.9.1.

The settings in *Settings → Image & Video* come with their patches wherever those apply: upscaling
(`sharp_scaling`) 2.0 – 2.3.4, the 1x PNG (`photo_1x`) 2.1.1 – 2.3.4, video codec and quality
(`video_quality`) 2.1.2 – 2.3.4, Seek's filters (`smoothing_settings`) and flat-field frames
(`flat_field`) 2.2.0 – 2.3.4, Smart smoothing 2.2.3 – 2.3.4.  The build test checks each
section class in the built app.  Only 2.3.4 has shown them on a phone.

`no_smoothing` is opt-in, the alternative to `smoothing_settings`: the build test applies every
patch but it, and `check` tests each patch alone.

`png_photos`, `photo_1x` and `video_quality` start at 2.1.1 / 2.1.2, where the photo and recording
code they hook first appears in this shape; `resume_fix` matches the same pause code in every
release, `no_analytics` the same Google Analytics thread.  2.3.1 was checked and built from its `.xapk` split bundle, 2.3.3 from its `.xapk`
and from its per-ABI APKs (`arm64-v8a`, `armeabi-v7a`).

Regenerate against your own folder of APKs:

```sh
SEEK_APK_DIR=~/apks pytest tests/test_real_apks.py -v              # check only
SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py -v # and build each one
```
