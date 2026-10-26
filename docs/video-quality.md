# `video_quality` — record at the photo's size and quality, every thermal frame

**Stock:** H.264, 480×640, a fixed 1.5 Mbit/s, 15 fps, a keyframe every 5 s; mono 44.1 kHz AAC at
64 kbit/s.
**Patched:** HEVC (or H.264), 960×1280 — the photo's pixels — at a constant quantizer, one frame per
thermal frame, a keyframe every second; stereo 48 kHz AAC at 256 kbit/s.

| Pixel 8 Pro, Compact, 2.3.4 | stock | `video_quality` (default `--video-qp 18`) |
|---|---|---|
| codec | H.264 High (hardware) | HEVC Main, `hvc1` (hardware), level 5.1 |
| size | 480×640 | 960×1280 |
| frame rate | 15.0 fps (the phone camera's) | 24.6 – 27.7 fps average: every thermal frame, pauses only at the shutter |
| bitrate | 1.5 Mbit/s, fixed | ~9 – 10 Mbit/s on a still scene (68 – 76 MB/min); more with motion |
| colour | untagged | tagged BT.709, limited range — decodes to the photo's colours |
| sound | AAC-LC mono 44.1 kHz, 64 kbit/s | AAC-LC stereo 48 kHz, 250 kbit/s, frames stamped by their samples |

## The encoder

`seekpatch.Video` replaces the app's `MediaCodec.createEncoderByType("video/avc")` + `configure`.
It takes the app's own format (to learn its size), and returns an encoder configured like this:

1. **Which encoder.**  Every hardware encoder first — the configured codec (`--video-codec hevc`,
   the default) before H.264 — then software ones.  Software encoders are a last resort: on the
   Pixel, Android's software H.264 encoder stops at 12 Mbit/s and 2048 px and its HEVC encoder at
   512 px.  The stock app also gets the hardware encoder: its files are H.264 *High* profile,
   which the software one does not produce.
2. **Size.**  The app's size scaled up so its long side is the photo's 1280: 480×640 becomes
   960×1280; in 16:9 the app already records 720×1280.  The encoder draws the live view's scene
   itself (the encoder thread calls the render thread's draw), so the overlays and `sharp_scaling`
   come along, and at the photo's size each pixel gets exactly the photo's scaling kernel.
3. **Rate control.**  There is no CRF in Android's encoder API, and this phone's encoders offer no
   constant-quality mode either; they do take QP bounds (Android 12+).  Pinning the bounds gives a
   constant quantizer — the hardware analogue of CRF:

   | frames | QP |
   |---|---|
   | I | `qp − 2` |
   | P | `qp` |
   | B (if the encoder uses them) | `qp + 2` |

   with a 40 Mbit/s ceiling, which keeps the signalled level at HEVC 5.1 / H.264 4.1 — playable
   everywhere those codecs are (an 80 Mbit/s ceiling made the encoder signal HEVC 6.0).  Encoders without QP bounds but with constant-quality mode get
   that, the quality mapped from the QP; encoders with neither get VBR at 12 Mbit/s for 960×1280.
   A bitrate chosen in the settings is VBR at that bitrate, on any encoder.
4. **The rest.**  `frame-rate` 30 (a hint: frames come as the camera sends them), a keyframe every
   second, BT.709 colour tags, realtime priority, HEVC Main / H.264 High profile.

If an encoder refuses the full setup it is retried with plainer ones (no profile; then no profile
or QP bounds; then nothing but size and bitrate); if every encoder refuses, the app's own format is used, so
recording never breaks.  `adb logcat -s seek-patch` shows what was chosen.

### Why not 4:4:4

No encoder on the phone does it: the Pixel's hardware H.264 tops out at High, HEVC at
Main / Main10 and AV1 at Main — all 4:2:0 (`python3 tools/codecs.py list`).  A software 4:4:4
encoder would mean bundling x264 (GPL, and heavy on the CPU).  At the photo's size it would not
change much anyway: 4:2:0 stores colour at 480×640, three times the Compact's 156×206 sensor
(twice the Compact Pro's 240×320) in each direction, so every sensor pixel keeps its colour.  Only
hard edges inside one display pixel — overlay text, the crosshair, the palette bar — lose some
colour sharpness.

### Choosing the QP

A QP-10 recording (25 Mbit/s) of a still scene was the reference; its frames were re-encoded on the
phone's hardware encoders at each QP and compared with it (`tools/codecs.py ladder`, 120 frames).
"Noise kept" is how much of the sensor's frame-to-frame noise survives: an encoder that smooths it
makes a video look calmer than the photos.

| encoder | QP | Mbit/s | MB/min | PSNR Y | PSNR UV | SSIM | noise kept |
|---|---:|---:|---:|---:|---:|---:|---:|
| HEVC | 14 | 15.3 | 115 | 53.3 | 49.4 | 0.9945 | 99.6 % |
| HEVC | 16 | 12.2 | 91 | 52.4 | 48.4 | 0.9933 | 99.6 % |
| **HEVC** | **18** | **9.0** | **68** | **51.6** | **47.3** | **0.9918** | **99.6 %** |
| HEVC | 20 | 7.1 | 53 | 50.8 | 46.5 | 0.9904 | 99.1 % |
| HEVC | 22 | 5.4 | 40 | 50.0 | 45.5 | 0.9885 | 98.8 % |
| HEVC | 24 | 4.1 | 31 | 49.1 | 44.5 | 0.9860 | 98.7 % |
| HEVC | 26 | 3.0 | 23 | 48.1 | 43.5 | 0.9830 | 98.0 % |
| HEVC | 28 | 2.2 | 16 | 47.1 | 42.3 | 0.9789 | 96.6 % |
| H.264 | 16 | 14.2 | 107 | 51.1 | 49.1 | 0.9928 | 102.2 % |
| H.264 | 18 | 11.1 | 83 | 50.3 | 47.8 | 0.9914 | 101.3 % |
| H.264 | 20 | 8.4 | 63 | 49.7 | 46.8 | 0.9897 | 101.2 % |
| H.264 | 22 | 5.6 | 42 | 48.9 | 45.7 | 0.9876 | 99.9 % |
| H.264 | 24 | 4.3 | 32 | 48.2 | 44.6 | 0.9853 | 97.5 % |

At 3× zoom QP 16 – 20 cannot be told from the reference; from 24 the edges between sensor pixels
start to soften.  18 is the default: above 50 dB with margin for noisier scenes, at 68 MB a
minute.  HEVC needs ~20 % fewer bits than H.264 for the same PSNR.
Motion costs more than a still scene — the reference itself ran at 25 Mbit/s at QP 10.

### Colour

The encoder converts the GL scene's RGB to YUV itself.  The palette bar is the same overlay in the
photo and the video, so it is a direct check: decoded with BT.709 the video's bar is within 0.7
levels (mean, 3 at most) of the photo's; decoded as BT.601 — what players assume for untagged
video of this size — it is off by 7 – 8.  The stream is tagged BT.709 / limited range, so players
pick the right one.

## The frame clock

The stock render thread hands the encoder a frame whenever the *phone* camera delivers one — the
same 15 fps clock that capped the live view (see [full-fps.md](full-fps.md)).  The patch hands one
over after every thermal upload instead (`seekpatchVideoFrame`, added to the render thread: it
waits for the upload to finish, `glFinish`, because the encoder draws from its own GL context) and
drops the camera's.  Timestamps are the frames' arrival times, so the video plays in real time and
the camera's shutter pauses (~0.4 s every few seconds) stay pauses.  This works with or without
`full_fps`.

## The microphone

`seekpatch.Audio` replaces `AudioRecord.getMinBufferSize` and `MediaCodec.configure` in the app's
recorder and sets the `AudioRecord`'s rate and channels: 48 kHz stereo if the phone can open it from
the camcorder microphone, else 48 kHz mono, else the app's own 44.1 kHz mono; AAC-LC at 256 kbit/s
stereo / 160 kbit/s mono (Android's AAC encoder takes up to 510).  Whether a recording has sound at
all is [`mic_prompt`](mic-prompt.md)'s business.

### The sound's bytes

**Stock:** the app reads each microphone block into a direct `ByteBuffer`, then copies it to the
encoder with `put(buffer.array(), 0, n)`: from index 0 of the buffer's backing array.  Android keeps
a direct buffer's bytes a few bytes into that array — `arrayOffset()` is 4 on a Redmi 4X (Android
7.1.2) — so each block reached the encoder one stereo sample late: a silent sample first, its last
sample lost.  That is a click at every block, 47 a second (blocks of 1024 samples on the Redmi: its
encoder's input buffers hold 4096 bytes), heard as a buzzy, high-pitched distortion.

**Patched:** `seekpatch.Audio.samples` (in place of that `array()`) gives the block's bytes from its
first.  On the Redmi, a recording of a 1 kHz tone from the phone's own speaker, band-passed to
12 – 20 kHz and folded by 1024 samples: 676× the median energy at the block boundary before, 4.4×
(no peak anywhere) after.

### The sound's timestamps

**Stock:** the app stamps each block it reads from the microphone with the time the read
*started*, before it waited for the samples, and some AAC encoders give each 1024-sample frame the
stamp of the block the frame starts in.  Android 7's software encoder (`OMX.google.aac.encoder`)
does: a video recorded with seek-patch 0.9.0 (whose sound timing is the app's own) on a Redmi 4X
(Android 7.1.2, 48 kHz stereo, 20 ms blocks) had its AAC frames 19 – 22 ms apart, and every 15th
40 ms apart, where each frame is 21.3 ms of sound.  A
player that keeps to the timestamps drops or stretches sound there: a stutter three times a
second.  The encoder also hands out its configuration (2 bytes) as a buffer, and the app writes it
into the file as the first sound frame: an error for decoders (`Input buffer exhausted before END
element found`), and the first real frame 0.7 s later.

**Patched:** `seekpatch.Audio.queue` (in place of the encoder's `queueInputBuffer`) stamps each
block with the time of its first sample, counted in samples from the first block, whose time is
when its read returned less the block's length.  A block that ends more than the microphone's
buffer (6× the minimum, as the app sets it up; 120 ms on the Redmi) before its read returned means
samples were dropped, and the count starts again from that block.  `seekpatch.Audio.dequeue` (in
place of `dequeueOutputBuffer`) stamps each AAC frame with the time of its first sample from the
same count, and keeps the configuration buffer out of the file (the muxer has it from the output
format).  A frame of silence goes in before the first block: Android 7's muxer writes no edit list
and stretches a track's first frame over the time before it (0.8 – 0.9 s on the Redmi: the sound
starts after the picture), so that frame is better silent than the first of the sound.

On the Redmi, 10 s recordings: every frame 21.333 ms after the last, no decoder errors, the first
four 1024-sample blocks silent (the silent frame and the encoder's own delay).  The app's writer
still drops the last three frames (~64 ms) when a recording stops.

## Options

| | |
|---|---|
| `--video-codec hevc` | default; H.264 is the automatic fallback.  The *Video codec* setting starts from it |
| `--video-codec avc` | H.264 first: plays on anything, ~20 % bigger |
| `--video-qp N` | 10 – 40, default 18; lower = better and bigger.  The setting below starts from it |

## Settings

*Settings → Image & Video* (2.1.2 – 2.3.4):

- **Video codec:** *H.265 (HEVC): smaller files* or *H.264 (AVC): plays everywhere, about 20 %
  bigger*; `--video-codec` is the default.  A phone without an H.265 encoder for the video's size
  records H.264 either way, and the H.265 choice says so: *H.265 (HEVC): not on this phone,
  records H.264*.
- **Video quality:** the QP, from *QP 14: about 115 MB a minute, best* to *QP 28: about 16 MB a
  minute, smallest*, in steps of 2, with the sizes of the ladder above (HEVC on a still scene;
  ×1.2 for H.264, when it is chosen or the phone has no H.265 encoder), then a bitrate: *2 Mbit/s:
  about 15 MB a minute* to *40 Mbit/s*, up to the encoder's highest.  A QP keeps the quality steady
  and lets the size follow the scene; a bitrate keeps the size steady.  `--video-qp` is the
  default, and it joins the list when it is not one of the choices.  A QP needs an encoder with QP
  bounds (Android 12+) or a constant-quality mode; where the encoder that will record has neither,
  the list has only the bitrates, and the default is *12 Mbit/s*, what a QP records at there.

The next recording uses the new values: `seekpatch.VideoSettings` sets `VideoConfig.mime`,
`VideoConfig.qp` and `VideoConfig.target` (a chosen bitrate; 0 for a QP), which `seekpatch.Video`
reads when the encoder is created.

On the Pixel, the same scene for ~9 s: QP 18 gave 5.4 Mbit/s and QP 28 1.3 Mbit/s (6.5 MB and
1.7 MB), a factor of 4.2.  The ladder has 9.0 and 2.2 Mbit/s (4.1×) for a scene with more detail.

## Notes

- A Redmi 4X (Snapdragon 625, Android 7.1.2) has no H.265 encoder, and its H.264 encoder
  (`OMX.qcom.video.encoder.avc`) takes no QP: Android 7 has no QP bounds, and it lists no
  constant-quality mode (quality range 0 – 0).  It refuses the High and Main profiles
  (`configureCodec returning error -38`) and records Baseline, VBR up to 20 Mbit/s.  Its list has
  2 – 20 Mbit/s, 12 by default; on the phone, 8 Mbit/s recorded 7.9 Mbit/s and 12 recorded 11.9.

- Thermal+ recording (blended with the phone camera) has not been tested on a phone.  The encoder
  draws the same scene as the screen, with the newest camera frame.
- Twice the photo's size, 1920×2560, would carry colour at the photo's full resolution, but the
  Pixel's HEVC encoder is rated 20 – 41 fps there — too close to the camera's ~28.
