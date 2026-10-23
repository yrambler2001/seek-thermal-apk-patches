# `png_photos` — lossless photos

**Stock:** photos are JPEG at quality 100 with 4:2:0 chroma — Android's JPEG encoder
(`Bitmap.compress`) has no 4:4:4 mode — about 0.3 – 0.6 MB each.
**Patched:** photos are PNG, lossless, about 0.55 – 0.6 MB each (1280×960, Compact).

The app can already do this.  *Settings → Save Uncompressed* (preference `lossless_comp_key`)
switches photos to PNG — but the switch is hidden: it appears only after tapping *About → Image
Processing Software* five times (the same taps unlock *Simulation Mode* and *Show Frame Rate*, and
five more hide them again).  The patch turns the setting on where the app reads it:

| | |
|---|---|
| the preference reader | a static `(Context) → boolean` around `getBoolean("lossless_comp_key")`: the app's start-up and the share copy of Thermal+ photos read it |
| the photo flag setter | the camera's `(boolean)` setter of the flag the photo method checks before choosing `.png`; the settings screen calls it directly when the switch changes |

Both return / store *true* on Android 11 and newer.  The app writes EXIF tags (orientation, make,
model) into every photo, and Android's `ExifInterface` can only write them into a PNG since Android
11; before that saving a PNG photo fails, so Android 10 and older keep whatever the setting says.

The PNG keeps the EXIF tags (Android 11+ writes them into the PNG's `eXIf` chunk), the in-app
gallery shows PNG photos like JPEG ones, and sharing sends the file as it is.  Thermal+ photos'
phone-camera image is saved as PNG too.

Versions: the reader and setter exist from 2.1.2 on.
