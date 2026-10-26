# Writing a patch

## The pipeline

```
(bundle ──APKEditor m──►) apk ──apktool d -r──► smali tree ──patches──► apktool b ──zipalign──► uber-apk-signer ──► apk
```

- A split bundle (`.xapk`, `.apks`, `.apkm`: any zip of apks without a manifest of its own) is merged
  first (`seekpatch/bundle.py`).  The base and the splits are told apart by their manifests, not
  their file names; they must be one package at one versionCode.  APKEditor merges the resources and
  native code of every split and drops the split-only manifest attributes.

- `apktool d -r` decodes the code only.  Resources and the binary manifest are carried over byte for
  byte, so a rebuild cannot break them.  A patch can still add to the binary manifest through
  `seekpatch/axml.py` (`Document`, `add_uses_library`), as `http_legacy` does.  `--side-by-side` decodes resources too (`apktool d`), to
  rename the package in the text manifest (`seekpatch/manifest.py`).
- Before patching, every library the code loads (`System.loadLibrary`) must be inside the apk — a
  base apk from a split install, whose native code lives in a config split, is refused.
- `seekpatch/zipalign.py` aligns in Python: stored entries to 4 bytes, `.so` files to 16 KiB pages (the
  app maps them straight out of the apk: `extractNativeLibs="false"`).  Stale `META-INF` signature and
  build-metadata files are dropped.
- uber-apk-signer signs (v1 + v2 + v3) with the per-user key in the seek-thermal-apk-patches home directory, created
  with `keytool` on first use.

## A patch module

`src/seekpatch/patches/<name>.py`, registered in `patches/__init__.py`:

```python
NAME = "my_patch"
SUMMARY = "one line for `seek-thermal-apk-patches list`"
VERSIONS = "2.2.0 - 2.3.4"     # the range you tested
RECOMMENDED = False            # part of the default set?
REQUIRES = ("other_patch",)    # optional: patches applied before it (apply() checks their marks)

def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    ...                         # find, check, edit
    return ["what was changed, one line each"]
```

`SmaliTree` (`seekpatch/smali.py`) holds every smali file in memory: `containing(*needles)`,
`path_of(descriptor)`, `get` / `set`, `replace_method_body`, `add_class`, and the app's
`version_code` / `version`.  `manifest` / `set_manifest(data)` read and replace `AndroidManifest.xml`
as decoded: binary by default, text with `--side-by-side`, so a patch that edits it handles both.  `add_native_library(abi, name, data)` adds a `.so` to `lib/<abi>/` (`abis` lists the
apk's ABIs); it is stored uncompressed, as the app maps its libraries out of the apk.  `methods(text)` iterates methods with their header and body.  Nothing
is written until `save()`; the CLI wraps each patch in `tree.transaction()`, so a patch that raises
leaves the tree exactly as it found it.  That is what lets the default set skip a patch that does not
apply to a given version, while patches named with `-p` must all apply.

## Java helpers

A hook of a few instructions is written in smali by the patch.  Anything bigger — choosing an
encoder, a permission flow, writing a file — goes into a helper class in
[`helpers/java/seekpatch/`](../helpers/java/seekpatch), and the patch only adds a call to it.

```
helpers/java/seekpatch/*.java ──javac (Java 8 bytecode)──► d8 --release --min-api 23 ──► apktool d
    ──► src/seekpatch/helpers/*.smali   (committed; patching needs no Android SDK)
```

- Run `python3 helpers/build.py` after changing a helper (needs a JDK and the Android SDK's
  `build-tools;35.0.0` + `platforms;android-35`) and commit the result; `--check` tells you if
  the committed smali is stale.
- The patch adds a helper with `add_helpers(tree, "Mic")` (from `seekpatch.helpers`); inner classes
  (`Mic$1`, …) come along.
- Values from the command line go into a small class the patch writes itself (e.g. `VideoConfig`,
  see `video_quality.py`).  Its compile-time stand-in is in `helpers/stubs/` and is not shipped.
  Read those values from non-`final` fields, so javac does not inline them.
- The same goes for calls into the app, whose names change every release: the patch writes a
  class that forwards to the method it found (e.g. `SeekIP` → the app's feature wrappers, see
  `flat_field.py`), and the helper compiles against the stub.
- The app's minSdk is 23: guard newer APIs with `Build.VERSION.SDK_INT`.  Constants (`MediaFormat.KEY_*`)
  are inlined by javac and safe on any version.
- Helpers must not fail the app: catch, log under the tag `seek-thermal-apk-patches`, and fall back to what the
  app did.

## Settings in the app

A patch can add switches and lists to the app's *Settings → Image & Video* screen.
`patches/settings.py` adds two hooks once, for whichever patch comes first: after the screen's
`addPreferencesFromResource` (`seekpatch.Settings.screen`) and in the camera screen's `onCreate`
(`seekpatch.Settings.attach`).  The patch then adds a section class with `load(SharedPreferences)`
and `screen(PreferenceFragment, SharedPreferences)`, listed in `Settings.SECTIONS`; Settings finds
it by name at run time, so an absent patch costs nothing.  Values go to seek-thermal-apk-patches' own
preferences file, not the app's; `Settings.addSwitch` / `addList` create the app's own preference
classes, not persisted by the framework.  Runtime code reads values that `load` cached, never the
file.  See `smoothing_settings.py` and `Filters.java`.

## Native code

`smart_smoothing` needs C: [`helpers/native`](../helpers/native) is built by
`python3 helpers/build_native.py` (NDK r25b, arm64-v8a + armeabi-v7a, API 23, stripped, sha1 build
id, 16 KiB pages) into `src/seekpatch/native/<abi>/`, committed like the smali; `--check` rebuilds
and compares byte for byte.  Native code never contains Seek code: it hooks the app's libraries
from outside (see [smart-smoothing.md](smart-smoothing.md)) and checks what it hooks before
changing anything.  `tests/test_native.py` builds the hook for the host and drives it with a
stand-in library.

## Rules

1. **Find code by behaviour, never by name.**  Seek's build is obfuscated and every release renames
   classes, methods and fields.  Anchor on what survives: string constants (`"ThermalPlusRenderThread"`,
   `"featureEnhancedProcessing"`), framework calls (`glTexImage2D`, `updateTexImage`), JNI method names
   (`seekIPsetFeature`), signatures, call sequences.  `patches/seek.py` has the shared lookups.
2. **Expect exactly one match.**  If a search finds zero or two, raise `PatchError` with what you
   looked for and what you found.  Never pick the first of several.
3. **Prove the code is what you think before changing it.**  `debug_log` only fills methods that are
   empty stubs; `smoothing_settings` refuses versions whose native library it has not verified;
   `sharp_scaling` checks the shader has exactly one sample and one `main`.
4. **Mark what you add.**  Every inserted line carries `mark(NAME)` (`# seek-thermal-apk-patches <name>`), which is
   how `ensure_unpatched` refuses a second application.
5. **Keep registers safe.**  Only use registers you know are free at the insertion point, or that the
   surrounding code no longer reads.  Non-range `invoke` needs registers ≤ v15.  Prefer adding a
   static helper class (`tree.add_class`) over growing a method's `.locals`.

## Testing

- Add the shape you match to the synthetic trees in `tests/fixtures/` (hand-written smali — no Seek
  code) and a test in `tests/test_patches.py`: it applies, it composes with the other patches, it
  refuses when its target is missing.
- `tests/test_build.py` assembles every patched fixture with apktool and signs it, so a smali syntax
  error fails here rather than on a phone.
- Run it against real apks: `SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py`, and
  update `docs/versions.md`.
- Run it on a phone.  `tools/fps.sh` and `tools/measure_kernel.py` turn "looks better" into numbers.
