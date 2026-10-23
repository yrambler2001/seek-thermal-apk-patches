# Versions

Every release below was decoded, checked, patched with all applicable patches, rebuilt, aligned and
signed by `tests/test_real_apks.py`.  2.3.4 was also run on a phone.

| app | versionCode | `full_fps` | `sharp_scaling` | `no_smoothing` | `debug_log` |
|---|---|:---:|:---:|:---:|:---:|
| 1.9.1 | 103 | ✓ | – ¹ | – | – ² |
| 1.9.2 | 104 | ✓ | – ¹ | – | – ² |
| 1.9.3 | 106 | ✓ | – ¹ | – | – ² |
| 1.9.4 | 108 | ✓ | – ¹ | – | – ² |
| 1.9.5 | 109 | ✓ | – ¹ | – | – ² |
| 2.0 | 156 | ✓ | ✓ | – ³ | ✓ |
| 2.0.1 | 158 | ✓ | ✓ | – ³ | ✓ |
| 2.0.3 | 160 | ✓ | ✓ | – ³ | ✓ |
| 2.1.1 | 162 | ✓ | ✓ | – ³ | ✓ |
| 2.1.2 | 180 | ✓ | ✓ | – ³ | ✓ |
| 2.1.4 | 210 | ✓ | ✓ | – ³ | ✓ |
| 2.1.5 | 217 | ✓ | ✓ | – ³ | ✓ |
| 2.1.6 | 240 | ✓ | ✓ | – ³ | ✓ |
| 2.1.7 | 250 | ✓ | ✓ | – ³ | ✓ |
| 2.2.0 | 260 | ✓ | ✓ | ✓ | ✓ |
| 2.2.1 | 265 | ✓ | ✓ | ✓ | ✓ |
| 2.2.2 | 272 | ✓ | ✓ | ✓ | ✓ |
| 2.2.3 | 276 | ✓ | ✓ | ✓ | ✓ |
| 2.3.0 | 285 | ✓ | ✓ | ✓ | ✓ |
| 2.3.4 | 294 | ✓ | ✓ | ✓ | ✓ |

1. 1.9.x saves photos with a different code path; the live-view part would work, but the patch is
   all or nothing.
2. 1.9.x has no frame-timing log to switch on.
3. The image library these versions ship handles feature 900 differently (2.1.6 / 2.1.7) or is not
   there at all (2.1.5 and older have no `libseekip.so`); the patch refuses them.

Regenerate against your own folder of APKs:

```sh
SEEK_APK_DIR=~/apks pytest tests/test_real_apks.py -v              # check only
SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py -v # and build each one
```
