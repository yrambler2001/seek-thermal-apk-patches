# `http_legacy` — the Apache HTTP library, declared

**Stock:** on Android 9 and later, 2.1.6 – 2.3.1 throw `NoClassDefFoundError` wherever they use
Apache HTTP (`org.apache.http.*`).  The first place is Google Analytics, about 15 s after launch,
and that kills the app (see [no-analytics.md](no-analytics.md)).  2.1.6 – 2.2.3 also use Apache
HTTP for the account pages (sign in, create account, change email or password), for downloads from
Seek's server (`sdl.thermal.com`), and in 2.2.3 for a JSON client.
**Patched:** the app declares the library, as Seek's own 2.3.3 does, and Android loads it:

```xml
<application ...>
    <uses-library android:name="org.apache.http.legacy" android:required="false"/>
```

## Why the library goes missing

Android 9 took Apache HTTP off an app's class path.  It still ships with the system, as the shared
library `org.apache.http.legacy` (`/system/framework/org.apache.http.legacy.jar`).  When Android
starts an app, it builds the app's class loader from the platform classes and the shared libraries
the app needs:

- an app that targets API 27 or lower gets this library without asking, which is why 1.9.1 – 2.1.5
  work;
- an app that targets API 28 or higher gets it only if its manifest declares it.

| app | targetSdk | declares it | on Android 9+ |
|---|---|---|---|
| 1.9.1 – 2.1.2 | 18 – 19 | no | added by Android |
| 2.1.4 – 2.1.5 | 27 | no | added by Android |
| **2.1.6 – 2.3.1** | 28 – 34 | **no** | **missing**: patched |
| 2.3.3 – 2.3.4 | 34 – 35 | yes | declared by Seek |

`required="false"` lets the app install on a device without the library, where it would then have
to do without.  Google recommends it, and every Android 9+ phone has the library.

## On a phone

2.2.2 was patched with `http_legacy` alone and run on a Pixel 8 Pro with Android 16:

- `dumpsys package` lists `usesOptionalLibraries: org.apache.http.legacy` and `usesLibraryFiles:
  /system/framework/org.apache.http.legacy.jar`;
- at start, the app's process logs `ApplicationLoaders: Returning zygote-cached class loader:
  /system/framework/org.apache.http.legacy.jar`.

Google Analytics then failed to bind to Play services twice, 5 s apart, as in the stock app
(`Unable to start service Intent { act=com.google.android.gms.analytics.service.START … } not
found`).  The stock app dies right after the second failure.  The patched one switched to its local
store and was still running a minute later.

## With `no_analytics`

The two patches fix different things, and both are in the default set:

- `http_legacy` alone stops the crash, but Google Analytics then works again.  Its fallback store
  keeps hits and posts them over HTTP.  The endpoint, Universal Analytics, was shut down by Google
  in 2023, but the data still leaves the phone.
- `no_analytics` alone stops Analytics, but not the account pages or the downloads.
- Together: nothing is sent, and nothing that uses Apache HTTP crashes.

## How the manifest is edited

By default seek-patch decodes only the code (`apktool d -r`), so the manifest stays in Android's
binary XML.  [`seekpatch/axml.py`](../src/seekpatch/axml.py) parses it into its chunks: string pool,
resource map, and one chunk per namespace, element start, element end and text.  It then adds the
element and writes the file back.

- Unchanged chunks are written back byte for byte.  Every Seek manifest from 1.9.1 to 2.3.4
  round-trips to the same bytes.
- Android finds `android:` attributes by the resource id the resource map gives their name.
  `android:name` and `android:required` are reused when the map has them, as every Seek manifest
  does.  Otherwise the name is added at the end of the mapped strings, and every later string
  reference moves up by one.
- The element's layout is the one aapt2 writes into 2.3.4's manifest: first child of
  `<application>`, the two attributes in resource-id order, and `required` as a boolean `0`.  Its
  comment field, which aapt leaves empty and Android ignores, holds `seek-patch http_legacy`.  That
  is how a second run tells its own element from Seek's.

With `--side-by-side` the manifest is decoded to text, and the patch adds the same line there, after
`<!-- seek-patch http_legacy -->`.

The patch refuses:

- an app that targets API 27 or lower (Android adds the library itself);
- an app that already declares the library (2.3.3, 2.3.4);
- an app whose code does not use Apache HTTP.

Versions: 2.1.6 – 2.3.1.
