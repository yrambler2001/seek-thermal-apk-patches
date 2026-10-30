# Contributing

Bug reports and patches are welcome.

**Reporting a problem:** include the output of `seek-thermal-apk-patches check YOUR.apk` (it names the app version
and says which patch found what) and, for on-phone problems, the phone model, Android version and
camera model.  Please do not attach APKs.

**Code:**

```sh
pip install -e '.[dev]'
ruff check .
pytest                     # unit tests on synthetic smali (tests/fixtures), no APK needed
SEEK_APK_DIR=~/apks SEEK_BUILD=1 pytest tests/test_real_apks.py    # against your own apks
SEEK_SUPERRES=~/superres pytest tests/test_native.py   # the native hook against the research stage on a burst
```

Java helpers (`helpers/java`): edit the Java, then run `python3 helpers/build.py` (needs the Android
SDK: `build-tools;35.0.0`, `platforms;android-35`) and commit the regenerated
`src/seekpatch/helpers/*.smali` with it (`helpers/build.py --check` tells you if they are stale).
Text a helper shows goes through `Lang.t` / `Lang.f`, with a translation in every file of
`src/seekpatch/strings` (see [docs/writing-patches.md](docs/writing-patches.md#text-on-the-screen)).
Native helpers (`helpers/native`): `python3 helpers/build_native.py` (needs the NDK r25b), and
commit the libraries with the sources.

New patches: read [docs/writing-patches.md](docs/writing-patches.md) first — patches find code by
behaviour, expect exactly one match, and refuse instead of guessing.  Every patch needs a fixture
test, a run against real APKs (`SEEK_APK_DIR=... SEEK_BUILD=1 pytest tests/test_real_apks.py`), a
page in `docs/`, a line in the README and a column in `docs/versions.md`.  The table in
[docs/README.md](docs/README.md) is written from the patch modules: run `python3 tools/patch_index.py`
after changing a patch's `SUMMARY`, `VERSIONS` or `RECOMMENDED` (`tests/test_docs.py` checks it).
Never commit APKs, decompiled Seek code or smali copied from the app — the fixtures are
hand-written.

**Images** go in `docs/images` as AVIF, metadata stripped.  Screenshots and photos:

```sh
magick IN.png -strip -quality 45 -define heic:speed=2 OUT.avif
```

Crops meant to show single pixels (2× crops, nearest-neighbour enlargements) lose their edges and
grain at that quality; give them `-quality 75 -define heic:chroma=444` instead.  No faces, no
notifications or other personal data in a screenshot.  Charts stay SVG.  The README's smoothing
figure (the colour photo aligned to the thermal ones, and the crops) is built by
`tools/readme_images.py` from the source photos; its docstring has the command.
