# `debug_log` — the SDK's own frame-timing log, in logcat

Opt-in (`-p debug_log` or `--all`); meant for diagnosis, not daily use.

The app's camera layer (the Seekware SDK inside it) logs through a tiny static class whose methods
are compiled to `return-void` in release builds.  The calls are all still there.  This patch gives the
two methods — `(String msg)` and `(String tag, String msg)` — a body: `android.util.Log.d`, with the tag
`Seekware` for the one-argument form.

```sh
adb logcat -s Seekware
```

```
D Seekware: DAQ: using 4 chunks
D Seekware: DAQ: awaiting USB copy complete!
D Seekware: DAQ: awaiting USB copy complete!
D Seekware: DAQ: awaiting USB copy complete!
D Seekware: DAQ: awaiting USB copy complete!
D Seekware: miliseconds per USB IMG transaction: 28
D Seekware: DAQ: waited: 22 ms to get a frame to render
D Seekware: DAQ: fps: 31.219512195121954
D Seekware: MEDIA: File exists at: /storage/emulated/0/Pictures/Seek Thermal/img_thermal_1792771263177.jpg
```

(excerpt from a Pixel 8 Pro with a Compact)

| line | meaning |
|---|---|
| `DAQ: fps: N` | frames requested from the camera per second (1 s window) |
| `miliseconds per USB IMG transaction: N` | one frame: the credit request plus all bulk chunks |
| `DAQ: waited: N ms to get a frame to render` | how long the render side waited for the next frame — ~ the frame interval when the camera is the limit |

The data-acquisition thread logs about 16 lines per frame.

The logger is found by what the frame-acquisition thread hands its constant messages to
(`"DAQ: awaiting USB copy"`), and the patch only fills methods that are empty stubs.  1.9.x builds
have no such log.
