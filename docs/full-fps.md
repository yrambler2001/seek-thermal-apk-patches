# `full_fps` — draw every thermal frame

**Stock:** the live view shows 15 fps although the camera delivers ~30.
**Patched:** ~28 fps on screen (every image frame; the rest are shutter frames).

## What happens in the stock app

The camera is fine.  With the `debug_log` patch the app's own counters show the Compact
delivering a frame every ~31 ms — 30 – 32 fps between shutter events — on the phone just as on a computer.
SurfaceFlinger tells a different story for what reaches the screen:

| Pixel 8 Pro, Compact 1.3.0.0 | frames from the camera | frames on screen |
|---|---|---|
| Seek Thermal 2.3.4 | ~30 fps | **14.9 – 15.0 fps** (two runs; 0 frames dropped by the display) |
| with `full_fps` | ~30 fps | **27.5 fps** |
| HTI's Seek-based app (`com.temp.action.thermal` 4.1.0.33, Seek's public SDK), for comparison | – | 28.6 fps |

"0 dropped" means the app only *handed over* 15 frames a second.  The live view is drawn by a GL
thread that names itself `ThermalPlusRenderThread` (class `q/g` in 2.3.4; `RenderManager` in 1.9.1,
the one release with names kept).  It has two inputs:

- **a thermal frame** arrives: the colorized frame is uploaded into a texture (`glTexImage2D`) — and
  nothing else;
- **a phone-camera frame** arrives (`SurfaceTexture.onFrameAvailable` of the phone's *own* rear
  camera): the camera texture is latched (`updateTexImage`), the frame is handed to the video
  encoder, and only then is the scene drawn and swapped to the screen.

So the screen updates at the phone camera's rate.  The app opens the rear camera even in the plain
thermal view — it is the source for the Thermal+ blend — and asks for the preview fps range closest
to 15–15, which the Pixel runs at exactly 15 fps (`dumpsys media.camera`: `Preview FPS range: 15 - 15`).
Every other thermal frame is overwritten in its texture before it is ever shown.

The app's own "Show Frame Rate" overlay does not reveal this: it counts processed thermal frames
(~30), not drawn ones.  HTI's app, built on Seek's public SDK, has no such coupling — it hands each
thermal frame to an `ImageView` — and runs at the camera's rate on the same phone.

Seek presumably built it this way for Thermal+ (the visible camera as the master clock) when the
Compact was a 9 Hz camera, so a 15 fps clock was faster than any thermal frame.  With a ~30 fps camera
it halves the frame rate.  On phones without a 15–15 range the app picks the nearest one, so the
rate there can wander with lighting.

## The patch

1. Right after the thermal upload, call the render thread's draw method.
2. Remove that call from the phone-camera handler.

The camera handler still latches the camera texture (Thermal+ blends with the newest camera frame)
and still feeds the video encoder, so recordings keep the camera's clock (15 fps).

The draw is the render thread's no-argument method the camera handler calls last; the upload is the
`(ByteBuffer, int, int)` method around `glTexImage2D`.  Three call shapes exist across releases and
all are handled:

| releases | handlers | calls into the render thread |
|---|---|---|
| 2.3.x | lambda methods of the render thread | `invoke-direct {p0}` |
| 2.1 – 2.2 | inner `Runnable` classes | static synthetic accessors |
| 1.9 – 2.0 | inner classes | package-private methods, `invoke-virtual` |

The draw goes in the thermal handler's existing `try` block, so the frame buffer it holds is still
released if drawing throws.

## Notes

- The display can still drop a few frames when an LTPO panel switches itself to a 30 Hz mode
  (SurfaceFlinger reports them as dropped); "Force peak refresh rate" in Developer options avoids it.
- Thermal+ (blending with the phone camera) and video recording keep working by design but have not
  been tested on a phone yet.
