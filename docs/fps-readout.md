# `fps_readout` — the frame-rate readout, every half second

**Stock:** with *Show Frame Rate* on (Settings; one of the switches [`hidden_settings`](hidden-settings.md)
shows), the live view writes the thermal frame rate in its corner, *27.9 Hz*.  It changes every
3 seconds (every second in 2.0.x), the average over them, so a shutter pause or a change of
setting shows late, averaged into the rest.
**Patched:** it changes every 0.5 s, the average over the last half second.

At ~28 frames a second a half second holds 14 frames, so the readout moves in steps of about
2 Hz and shows each shutter pause as a dip (the shutter freezes the image for ~0.44 s).

## How it works

The camera thread counts its frames.  On each frame it compares the time since the last reading,
as a double, with 3000.0 (ms); once it is reached, the rate becomes frames / (elapsed / 1000.0), and
the count starts again.  The patch replaces the 3000.0 with 500.0.

| where | what |
|---|---|
| the frame counter: `currentTimeMillis()`, `(now - last)` as a double compared with `3000.0` (2.0.x: `1000.0`), then divided by `1000.0` | the window constant becomes `500.0`; the `1000.0` the time is divided by stays |

## Versions

2.0 – 2.3.4: the readout is not in 1.9.x.

On a phone (2.3.4, Pixel 8 Pro, Seek Compact): a screen recording read every 0.2 s shows each
number for two or three readings, 30.3 – 32.3 Hz, with dips to 11.4, 18.9 and 24.1 Hz where a
shutter pause fell into the half second.
