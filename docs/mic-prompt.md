# `mic_prompt` — ask for the microphone when a video starts

**Stock (2.3.1 – 2.3.4, Android 11+):** the photo, video and gallery buttons all check the
microphone permission first.  Without it the app asks for it and drops the tap — there is no
`onRequestPermissionsResult`.  After two denials Android stops showing the dialog; from then on the
app asks, Android answers "no" without a dialog, and none of the three buttons does anything.
**Patched:** photos and the gallery never need the microphone.  Starting a video without it asks;
the video then starts by itself, with sound if allowed.

| situation | what happens |
|---|---|
| microphone allowed | records with sound, nothing asked |
| photo, gallery, stopping a video | goes ahead — no microphone needed |
| video, Android can still ask | Android's dialog; then the video starts — with sound, or without and a toast saying so |
| video, Android will not ask again | a dialog: *Open settings* (the app's permission page) or *Record without sound* |

Android lets an app ask twice; after the second "Don't allow" only the settings page can change it,
which is why the patch offers that page instead of asking.  It remembers that Android stopped asking
(the app's preferences) and forgets it once the permission is granted.

## How

- The method behind the three buttons — `(String, int action)`, it checks `RECORD_AUDIO` — calls
  `seekpatch.Mic.gate(activity, action, recording)` instead of `checkSelfPermission`, and
  `Mic.request` instead of `requestPermissions`.  "Recording" is the flag the video button's
  start/stop toggle reads.
- An `onRequestPermissionsResult` added to the activity passes the answer to `Mic.onResult`.
- The answer arrives before the app has resumed: Android's dialog is an activity of its own, so the
  app paused and stopped the camera.  Starting the recording then fails ("video failed to save"),
  so `Mic` waits for the first thermal frame after the camera runs again — `Mic.frame()` is called
  after every thermal upload — switches the app back to video mode (the pause put it in photo mode)
  and starts the video.

Returning from that dialog crashed the stock app's live view; [`resume_fix`](resume-fix.md) fixes
that, and is part of the default set.

Versions: 2.3.1 – 2.3.4.  Older releases check and request the microphone together with storage
and never block on it, so the patch does not apply.  Source:
[`helpers/java/seekpatch/Mic.java`](../helpers/java/seekpatch/Mic.java).
