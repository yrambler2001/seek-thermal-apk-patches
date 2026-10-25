# `no_analytics` — no Google Analytics

**Stock:** every release bundles Google Analytics, and up to 2.3.1 the app reports screen views and
events while *Settings → Send Usage Data* is on, as it is by default.  On Android 9 and later
**2.1.6 – 2.3.1 crash about 15 seconds after they start**:

```
FATAL EXCEPTION: Service Reconnect
java.lang.NoClassDefFoundError: Failed resolution of: Lorg/apache/http/impl/client/DefaultHttpClient;
    at com.google.analytics.tracking.android.PersistentAnalyticsStore.<init>(PersistentAnalyticsStore.java:8)
    ...
    at com.google.analytics.tracking.android.GAServiceProxy.onConnectionFailed(GAServiceProxy.java:6)
    at com.google.analytics.tracking.android.AnalyticsGmsCoreClient.connect(AnalyticsGmsCoreClient.java:10)
```

**Patched:** Google Analytics never starts.  Nothing is sent, nothing is stored for later, and
nothing connects to Google Play services.  The crash is gone.

## Why it crashes

The app uses the Google Analytics SDK v3 (`com.google.analytics.tracking.android`).  Its thread,
`GAThread`, waits 5 s and then binds to the analytics service of Google Play services.  Play
services no longer has that service.  After two failed tries, 5 s apart, the SDK falls back to its
own hit store, whose dispatcher is Apache's `DefaultHttpClient`.

Apache HTTP left Android's default class path in Android 9.  An app that targets API 28 or higher
gets it only by declaring `<uses-library android:name="org.apache.http.legacy">`; an app that
targets 27 or lower gets it without asking.  The exception is thrown on the SDK's timer thread,
where nothing catches it, so the whole app dies.

| app | targetSdk | declares `org.apache.http.legacy` | on Android 9+ |
|---|---|---|---|
| 1.9.1 – 2.1.2 | 18 – 19 | no | works (gets the library anyway) |
| 2.1.4 – 2.1.5 | 27 | no | works (gets the library anyway) |
| **2.1.6 – 2.3.1** | 28 – 34 | no | **crashes ~15 s after launch** |
| 2.3.3 – 2.3.4 | 34 – 35 | yes | works, and the app no longer reports anything |

Turning *Send Usage Data* off also avoids the crash, because the app then never starts the SDK.  But
you have to get to Settings within those 15 s, and turning the switch off sends one last "usage data
changed" event first, so that session still crashes.  From the next launch on it stays quiet.

## What the patch changes

Everything that leaves the phone goes through one object, the SDK's service proxy: the Play services
connection, and the hit store with its HTTP dispatcher.  Only `GAThread.run()` creates it.  The patch
replaces `run()`:

1. It sets the SDK's own *disabled* flag, which the SDK sets itself when its set-up fails.
2. It takes whatever the app queues (hits, dispatches) and drops it, without running it.

The app's calls into the SDK are left as they are and go nowhere.  The *Send Usage Data* switch
stays in Settings (in the releases that have it, up to 2.3.1), but it no longer does anything.

The SDK keeps its own names in every release, but the patch still finds the thread by its behaviour:

- the thread's name, `"GAThread"`;
- the log line of its set-up failure, `"Google Analytics will not start up."`;
- the work loop: a *closed* flag, a `LinkedBlockingQueue.take()`, a *disabled* flag.

It also checks that the service proxy is created there and nowhere else.  `run()` compiles four
slightly different ways across the releases, and the patch matches all of them.

The app's own network code also uses Apache HTTP in 2.1.6 – 2.2.3: the account pages (sign in,
create account, change email or password), downloads from Seek's server (`sdl.thermal.com`), and in
2.2.3 a JSON POST client.  [`http_legacy`](http-legacy.md), also in the default set, declares the
library, so those work too.

On a phone (Pixel 8 Pro, Android 16), 2.2.2 with `no_analytics` alone ran its main screen for a
minute.  The log shows no attempt to bind to the analytics service and no crash.  The stock app,
and 2.2.2 with only `http_legacy`, tries twice within 10 s.

Versions: 1.9.1 – 2.3.4.
