# `steady_fps` — a steady, evenly spaced live view

**Before (stock, with `full_fps`):** the Compact sends ~32 frames a second, but the live view stutters, and
the frame-rate readout jumps between 28, 30 and 32.  The camera's app on an iPhone shows the same
camera at a steady 32, dropping frames only when the shutter clicks.

**Patched:** every frame the camera sends reaches the screen, at an even pace.  Fewer frames are lost
on the way.

Measured on a Pixel 8 Pro (Android 16) with the Compact, 2.3.4 with the default patches, 12 s
Perfetto traces, before and after:

| | before | after |
|---|---|---|
| screen refresh while the live view runs | 30 Hz most of the time, 60 Hz now and then | 60 Hz |
| screen updates | 27.0 a second for 29.4 frames received | 28.9 – 29.3 a second, one per frame received |
| gaps between screen updates (the shutter's pauses not counted) | 33 ms: 267, 17 ms: 19, 50 ms: 15, 67 ms: 16 | 33 ms: 275 – 276, 17 ms: 55 – 57, 50 ms: 2 – 3, 67 ms: 1 – 2 |
| frames the camera skipped (a 60 ms gap), not counting the shutter | 15 | 5 – 6 |
| longest wait of the camera's USB thread for a CPU | 21.7 ms | 3.2 ms |

At 60 Hz a 32 fps picture cannot be shown more evenly: each frame stays up for two refreshes
(33 ms), and every 7th or 8th for one (17 ms).  The 50 and 67 ms gaps left are frames the camera
did not send, and the shutter (a 0.44 s pause every few seconds, as on the iPhone).

## Why it stuttered

### The screen ran at 30 Hz

The Pixel's screen can refresh at 120, 60, 40, 30, 24 or 20 Hz, and Android picks the rate from what
the apps on screen ask for.  The live view asks for nothing, so Android measures it: about 30 frames
a second, so 30 Hz.  The camera sends a little more than 32.  Two frames a second have no refresh
of their own: one is dropped and the frame before it stays up for 67 ms.  On top of that, Android
caps an app that has a camera open at 60 Hz (the 30 – 60 Hz range in `dumpsys display`, under
`PRIORITY_APP_REQUEST_RENDER_FRAME_RATE_RANGE`), and Seek keeps the phone's rear camera open even in
the plain thermal view, for Thermal+.

### The camera's USB thread waited for a CPU

The camera library asks the camera for each frame separately: a control request (`0x53`,
*start get image transfer*), then four bulk reads of a quarter frame each, which come in as the
camera reads its sensor out, 7.7 ms apart.  The next request goes out as soon as a frame is in.  If
it goes out more than about 7 ms late, the camera skips a frame.

Two threads are on that path: the loop that queues each request, and `SeekwareDeviceHandler`, which
sends it.  The library gives the handler Java's top priority (`setPriority(10)`), but it is a
`HandlerThread`, and a `HandlerThread` sets its thread's priority back to normal when it starts.
The phone camera's HAL threads, busy with the preview nobody sees (about 1.2 CPU cores on this
phone), run at nice −15 and −20.  The handler waited for a CPU for up to 22 ms, so the request went
out late and the frame was skipped, about once a second.

Some skips are left, 5 – 6 in 12 s.  In those the request went out on time, but the camera started
sending a frame later than usual.  That is in the camera, and it happens less often with the frames
paced (below) than without, 3 – 6 against 8 – 15 in 12 s on the same build.

### Frames took 11 – 31 ms to reach the screen

From the last USB read to the finished frame on its way to the screen took 11 – 27 ms for most
frames, up to 31: the image library, the colours and the draw, on threads that also wait for a CPU
now and then.  Frames that arrive 31 ms apart were handed to the screen 21 – 39 ms apart.

## The patch

Source: [helpers/java/seekpatch/Steady.java](../helpers/java/seekpatch/Steady.java).

1. **The screen rate.**  Just before the render thread makes its EGL surface, the live view's
   window asks for 120 frames a second (`Surface.setFrameRate`, Android 11+).  Android gives the
   nearest rate it allows: 60 Hz on the Pixel while the app holds the camera, 120 Hz with
   [`phone_camera`](phone-camera.md) in the plain view.
2. **Priorities.**  The USB thread (an `onLooperPrepared()` added to it) and the loop that queues
   each request (at the top of its `run()`) run at nice −19, Android's priority for audio threads.
   They use little CPU, and every frame waits on them.  The render thread runs at −10, like
   Android's own render thread.  The image processing thread stays at Seek's −8.
3. **Pacing.**  The library's "frame complete" method notes the time.  The render thread's draw
   sets each frame's presentation time (`eglPresentationTimeANDROID`), which Seek sets to "now".
   The patch sets it to the frame's arrival plus a steady delay: the third slowest of the last 32
   frames, plus 20 ms for Android to put a finished frame on the screen, kept between 30 and 80 ms.
   On the Pixel that comes to about 40 ms.  Android shows each frame at the first refresh after
   that time, so the frames keep the camera's even rhythm.  A frame that is not ready by then is
   shown at once, as without the patch.

A frame now reaches the screen roughly 5 – 10 ms later than before the patch.  Recordings are not
affected: the video encoder sets its own timestamps.

## Notes

- With the rear camera closed, Android allows 120 Hz, where 32 fps shows as 33 and 25 ms frames
  instead of 33 and 17.  [`phone_camera`](phone-camera.md) opens the camera only in Thermal+.  With
  both patches, on the same phone: 120 Hz, gaps of 33 ms (234 – 237) and 25 ms (90 – 91) in 12 s,
  4 frames skipped by the camera.
- Tested on the phone with 2.3.4 only.  Every other release from 1.9.1 has the same three pieces
  (the render thread's window and presentation time, the `SeekwareDeviceHandler` thread, the frame
  loop and its "frame complete" method).  The build test patches all of them.
- Thermal+ was not tested.  The patch changes only when its frames are shown.

## Measuring it

A 12 s trace while the live view runs:

```sh
cat > cfg.pbtx <<'EOF'
buffers { size_kb: 131072 fill_policy: RING_BUFFER }
data_sources { config { name: "linux.ftrace" ftrace_config {
  ftrace_events: "sched/sched_switch" ftrace_events: "sched/sched_wakeup" ftrace_events: "sched/sched_waking"
  atrace_categories: "gfx" atrace_categories: "view" } } }
data_sources { config { name: "android.surfaceflinger.frametimeline" } }
data_sources { config { name: "linux.process_stats" process_stats_config { scan_all_processes_on_start: true } } }
duration_ms: 12000
EOF
adb push cfg.pbtx /data/local/tmp/
adb shell 'cat /data/local/tmp/cfg.pbtx | perfetto --txt -c - -o /data/misc/perfetto-traces/live.pftrace'
adb pull /data/misc/perfetto-traces/live.pftrace
```

Open it in [ui.perfetto.dev](https://ui.perfetto.dev):

- frames received: `SeekwareDeviceHandler` waking the image processing thread;
- the screen's rate: the `RenderRate` counter;
- screen updates: SurfaceFlinger's display frames.

Without a trace, `adb shell dumpsys SurfaceFlinger --latency '<the SurfaceView layer>'` lists the
last 127 frames of the live view: the presentation time asked for, the time shown, and when each
frame was ready.  `dumpsys SurfaceFlinger --list` gives the layer's name.
