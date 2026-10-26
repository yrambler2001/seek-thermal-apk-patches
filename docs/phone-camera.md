# `phone_camera` — the phone's camera runs only in Thermal+

**Stock:** the app opens the phone's own rear camera with the live view and keeps its preview
running, also in the plain thermal view, where nothing uses it.

**Patched:** the phone's camera opens when you turn Thermal+ on, and closes when you turn it off.

What the hidden preview cost, on a Pixel 8 Pro with the Compact, in the plain thermal view (12 s
Perfetto traces):

| | camera open (stock) | camera closed (patched) |
|---|---|---|
| CPU besides the app | camera HAL 13.9 s, I²C bus 2.5 s, cameraserver 1.7 s: about 1.5 cores | none |
| screen refresh for the live view | at most 60 Hz | 120 Hz |
| screen gaps for a ~32 fps camera (with `steady_fps`) | 33 ms, every 7th or 8th 17 ms | 33 ms, every 4th 25 ms |

Android caps an app that has a camera open at 60 Hz (`dumpsys display`:
`PRIORITY_APP_REQUEST_RENDER_FRAME_RATE_RANGE`, 30 – 60 Hz), so with the camera open no app setting
can get the screen above 60.  The camera's busy threads also run at nice −15 and −20, and kept the
camera library's USB thread from the CPU (see [steady-fps.md](steady-fps.md)).

## What uses the phone's camera

The live view's render thread (`ThermalPlusRenderThread`) owns a handler for the phone's camera
(`VisibleCameraHandlerThread`).  The names are 1.9.1's; later releases obfuscate them, and the calls
are the same up to 2.3.4:

- the render thread's constructor: `openCamera(Context)` opens it;
- its GL setup, once it has the camera texture (a `SurfaceTexture`): `beginCameraPreview(texture)`
  starts the preview, opening the camera first if it is not open;
- its stop: `pausePreview()` stops the preview and releases the camera;
- the front / back switch (from 2.1.2): releases the camera and opens the other one.

The picture goes into that texture, and the live view's scene blends it in by the stream's Thermal+
amount.  `setUseThermalPlus(boolean)` sets that amount, or 0 for the plain view.  A Thermal+ photo
also saves the camera's last frame; in the plain view the photo code does not ask for one.  Video:
the stock recorder takes its frames from the phone's camera, but with
[`video_quality`](video-quality.md) it takes every thermal frame.  The live view is redrawn per
thermal frame only with [`full_fps`](full-fps.md); without it, per phone-camera frame.  So
`phone_camera` needs both: `seek-thermal-apk-patches` refuses it without them.

## The patch

Source: [helpers/java/seekpatch/PhoneCamera.java](../helpers/java/seekpatch/PhoneCamera.java).

1. The render thread no longer opens the camera in its constructor.  In its GL setup it calls
   `PhoneCamera.ready(this)` instead of starting the preview: the camera stays closed.
2. `setUseThermalPlus(boolean)` first calls `PhoneCamera.thermalPlus(renderThread, on)`.  On a thread
   of its own, that runs the render thread's `seekpatchCameraOn()` (added: `beginCameraPreview` with
   the render thread's camera texture) or `seekpatchCameraOff()` (added: `pausePreview`, which waits
   until the camera is released).  The app calls `setUseThermalPlus` with the saved mode whenever
   the stream starts, so the camera follows the mode from the first frame.
3. The front / back switch does nothing while the camera is closed.

## Verified

On the Pixel 8 Pro with 2.3.4:

- **Plain view:** `dumpsys media.camera` lists no camera client, and the screen runs the live view
  at 120 Hz.  A plain-view video recorded normally: HEVC 960×1280, every thermal frame.
- **Thermal+ on:** the camera opens (Android lists the app's camera client), and its frames reach the live view (15 a second;
  the phone lay face up, so its picture was dark).  The screen drops to 60 Hz.
- **Thermal+ off:** the camera closes, and the screen goes back to 120 Hz.

Not tested on a phone: the front / back switch, a Thermal+ photo, other releases.  The build test
patches all of 2.1.2 – 2.3.4.

## Versions

2.1.2 – 2.3.4: `video_quality` starts at 2.1.2.  The render thread, the camera handler and
`setUseThermalPlus` have the same shape back to 1.9.1.
