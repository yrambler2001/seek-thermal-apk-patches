# Contributing

Bug reports and patches are welcome.

**Reporting a problem:** include the output of `seek-patch check YOUR.apk` (it names the app version
and says which patch found what) and, for on-phone problems, the phone model, Android version and
camera model.  Please do not attach APKs.

**Code:**

```sh
pip install -e '.[dev]'
ruff check .
pytest
```

New patches: read [docs/writing-patches.md](docs/writing-patches.md) first — patches find code by
behaviour, expect exactly one match, and refuse instead of guessing.  Every patch needs a fixture
test, a run against real APKs (`SEEK_APK_DIR=... SEEK_BUILD=1 pytest tests/test_real_apks.py`), and a
line in `docs/versions.md`.  Never commit APKs, decompiled Seek code or smali copied from the app —
the fixtures are hand-written.
