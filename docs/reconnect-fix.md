# `reconnect_fix` — the camera comes back

**Stock:** once the camera screen has closed, the app loses track of the camera until its process
is killed: swiped away from Recents, or stopped by Android.  How that shows depends on the version:

- 2.3.0 – 2.3.4: press Back on the app's home page with the camera connected, then open the app
  again: *Connect Your Camera*, with the camera plugged in.  Or unplug the camera while the app is
  in the background and go back to it: the app closes its camera screen by itself; open it again,
  plug the camera in, and the screen stays at *Connect Your Camera*.
- 2.2.0 – 2.2.3: press Back on the app's home page, open the app again (the picture is back), then
  unplug the camera and plug it in: the live view stays black.
- 1.9.1 – 2.1.7 do not have the bug.

**Patched:** the camera comes back.

## Why the camera does not come back

The names are 1.9.1's, the last release with names kept.

- `SeekwareLibrary` is the app's camera library.  It is a singleton for the life of the process, and
  the `BroadcastReceiver` for its USB events.  It registers itself, on the application context,
  once: when the singleton is created (`initWithAppName()`).
- It asks Android for permission to use a camera with a broadcast `PendingIntent`
  (`com.tyriansystems.Seekware.SeekwareLibrary.USB_PERMISSION`), and opens the camera when the
  answer arrives.  The same receiver hears the camera being unplugged.
- `DeviceManager.onDestroy()` — the camera screen, `MainActivity`, closing — puts the cameras to
  sleep, stops the library's threads and calls `SeekwareLibrary.unRegisterUSBIntent()`.  The
  process stays.
- Up to 2.1.7 the next screen registers it again: `MainActivity.onStart()` calls
  `DeviceManager.onStart()`, which calls `SeekwareLibrary.reRegisterUSBIntent()`.  2.2.0 dropped
  that call and the method.  From 2.2.0 the next `MainActivity` gets the same library and nothing
  registers the receiver again.

From 2.2.0, then, the app hears neither permission answers nor the camera being unplugged once a
camera screen has closed.  What that breaks first depends on the `DeviceManager`:

- From 2.3.0 each `MainActivity` creates its own.  The new one has no camera, and the camera the
  closed screen left in the library's device list, asleep, keeps the library from searching: one is
  listed.  (A search would ask for permission and never hear the answer.)
- In 2.2.x the `DeviceManager` is a singleton too, and it keeps the camera: the next screen wakes
  it, and the picture comes back.  What breaks is the next unplug.  Unheard, it leaves the camera in
  the device list.  When the camera comes back, Android gives it the same USB address, as it did
  on the phone, so the library takes it for the camera it already has and asks for nothing.

From 2.3.0, `MainActivity.onRestart()` also finishes the activity when there is no camera.  That is
the app closing by itself when you come back after unplugging, and how the unplug case gets there.
Up to 2.2.3 it does so only after Back on the app's reminder screen.

On the phone:

- 2.3.4, after Back, Back with the live view on: the app's process was still running, and `dumpsys
  activity broadcasts` listed no receiver for the `USB_PERMISSION` action in it.  Reopening showed
  *Connect Your Camera* with the camera plugged in.
- Stock 2.2.2: after Back and reopening, the picture was back, and a second Back logged
  `IllegalArgumentException: Receiver not registered: com.tyriansystems.Seekware.m` (nothing left to
  unregister).  After unplugging the camera and plugging it in, Android's unplug broadcast went to
  five receivers, none of them the app's.  The app asked for no permission, and the live view stayed
  black.  Stock 2.2.2 also crashes about 15 s after launch on Android 9+ while *Send Usage Data* is
  on (see [no-analytics.md](no-analytics.md)), and each crash starts a fresh process that hides
  this.  Earlier tries crashed that way; this run did not crash.
- Stock 2.1.6, the same steps: the camera came back.  The second Back logged `Receiver not
  registered` too, but each new screen registered it again, and the answer to the permission request
  after plugging the camera back in was delivered to the app.

## The patch

1. From 2.2.0, `unRegisterUSBIntent()` is emptied.  The receiver stays registered while the process
   lives.  It is registered on the application context, so no screen is leaked, and between screens
   unplugging is still heard, which keeps the device list right.  Up to 2.1.7 it is left as is: the
   app registers the receiver again itself.
2. From 2.3.0: `registerNotifcationListener()` (Seek's spelling), which each new `DeviceManager`
   calls, first releases the cameras left in the list.  Each is closed as unplugging closes it (the
   device's own close), its USB interface is released and its connection closed (the library's USB
   wrapper; unplugging skips this, as the camera is gone by then), and the list is emptied.  The
   library's own search then runs: Android answers the permission request at once, as it is still
   granted, and the camera opens.

The release waits for the next screen instead of running in `onDestroy()`.  By then the sleep
command the closing screen queued has run.  Closing the camera in `onDestroy()` would drop it, and
the camera would stay awake.

In 2.2.x the `DeviceManager` keeps its camera for the next screen, so there is nothing to release:
the patch keeps the receiver, and the camera plugged back in after an unplug is opened again.

## Only its own app's answers

Every Seek app asks for permission with the same action, as a broadcast addressed to nobody in
particular, and registers its receiver for other apps to reach.  With two Seek apps installed, the
store app and a `--side-by-side` build say, the answer to one app's request reaches both.  An app
that also has permission for the camera then opens it, in the background, from under the app in
front, which then shows nothing.  A receiver kept for the life of the process listens for longer,
so the patch also makes it hear only its own app:

3. The permission request's `PendingIntent` is addressed to the app's own package
   (`Intent.setPackage()`), so the answer reaches no other app.
4. On Android 13 and later the receiver is registered with `RECEIVER_NOT_EXPORTED`.  Unplugging,
   which Android sends, and the app's own answers, sent as the app, still arrive; another app's
   answers do not.  Older Android has no such flag, but there too the app's own answers reach only
   itself.

This part applies to every version, 1.9.1 – 2.1.7 included.  There it also covers the registration
each new screen repeats.

Stock, on the phone: the store app's answer was delivered to Seek (patched)'s receiver as well.

## On a phone

2.3.4, side-by-side, on a Pixel 8 Pro (Android 16) with a Seek Compact:

- Back, Back with the live view on.  The process stays (the same pid), with the receiver still
  registered.  Reopening the app shows the live view at 26 – 28 Hz, as after a fresh start, without
  a permission dialog.
- Unplugging the camera with the app in the background, coming back and plugging it in: the live
  view comes back without restarting the app.
- The answer to Seek (patched)'s request carries `pkg=com.tyriansystems.SeekThermal.patched` and was
  delivered to its receiver only, and the live view started.  With Seek (patched) running in the
  background, the answer to another Seek build's request (a stock receiver) was delivered to that
  app only.

Versions: 1.9.1 – 2.3.4.  Keeping the receiver, 2.2.0 – 2.3.4; releasing a camera left open,
2.3.0 – 2.3.4; hearing only its own app, all.
