# `usb_prompt` — one USB permission dialog for the camera

**Stock:** when the app starts and Android has not yet given it the camera (the camera was plugged
in since the app last ran: Android forgets the permission on unplugging), two *Allow the app Seek
Thermal to access the USB device?* dialogs come up, one after the other.  The first one opens the
camera; the second stays over the live picture, and answering it does nothing.

**Patched:** one dialog.

## Why there are two

Read in 2.3.4; the library's names are 1.9.1's, the last release with names kept.

- The camera library, `SeekwareLibrary`, searches for cameras (`searchForDevices()`), and asks
  Android for permission (`UsbManager.requestPermission`) for every camera it has not opened.  It
  hears the answer in its receiver and opens the camera.
- The search runs when the camera screen is created (`MainActivity.onCreate()` makes its
  DeviceManager, which registers its listener with the library: a search when no camera is
  listed) and again each time the screen resumes (`onResume()` → the DeviceManager → the library,
  a search whatever is listed).
- On a fresh start the second search comes before the first answer.  The camera is not open yet,
  so the library asks again, and Android queues a second dialog.  The first dialog pauses the
  screen, and once it is answered the camera opens; the second shows when the first is gone.  Its
  answer finds the camera open and is ignored.

On a Redmi 4X (Android 7.1.2, 2.3.4 with the 0.9.0 patches): `UsbPermissionActivity` was started
0.8 s apart for one launch, and after OK on the first the second came up over the live picture.
With the patch, after unplugging the camera and plugging it in again: one dialog.

## The patch

1. Each permission request of the library goes through `seekpatch.UsbPrompt.requestPermission`.
   While a request for the same camera (by its USB device name) waits for its answer, a second one
   is skipped.  A camera the app already has permission for is always passed on: Android answers
   that at once, with no dialog.  A wait counts as lost after 60 s and the request is made again
   (Android answers every dialog, also one dismissed, so this is a safety net).
2. The library's `onReceive()` first calls `seekpatch.UsbPrompt.heard`: a permission answer, or the
   camera being unplugged, ends the wait for that camera.

Up to 2.1.7 a thread of the library asks too; every request the patch takes has the library's own
`PendingIntent`, so its answer reaches the receiver that ends the wait.  The patch refuses an app
that asks for USB permission with any other answer.

From the code (not tried on a phone): Cancel works as in the stock app, where the screen resumes,
searches and asks again.  Only 2.3.4 has run on a phone.
