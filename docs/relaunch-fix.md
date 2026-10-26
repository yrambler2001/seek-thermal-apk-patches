# `relaunch_fix` — a picture after the app was killed, not a -40 °C screen

**Stock:** open the app again soon after it was swiped away from the recent apps, or force-stopped,
with the camera still plugged in, and it often starts with a flat magenta picture.  Every pixel and
the spot read -40 °C, the temperature bar says -40 °C at both ends, and frames keep coming (the
frame-rate readout counts them).  It stays that way until the camera is unplugged.

**Patched:** the picture, every time.

## What goes wrong

USB numbers the packets of a bulk endpoint DATA0, DATA1, DATA0, … (the *data toggle*), so the
receiver can tell a repeated packet from a new one: one whose number it has just seen is a repeat,
acknowledged and dropped.  When the app's process dies while the camera streams, the phone and the
camera can be left one step apart.  At the next start, the camera's first packet then carries the
number the phone takes for a repeat, and the phone drops it, without an error.

That packet is the first 512 bytes of the first frame, header included.  The first chunk of the
frame (13680 bytes for a Compact PRO) comes in 512 bytes short; the rest of the frame, and every
frame after it, arrive whole.  The camera starts each stream with frames of types 4, 9, 14, 25 – 28,
8 and 7 before the picture frames (type 3, with 6, 1, 20 around each shutter).  Type 4 comes once,
first, and the camera library needs it to start its thermography.  Without its header `SeekIPprocess()` answers 1407 (a bad
header), and from then on every pixel reads -40 °C: its lowest temperature, which most palettes show
as magenta.

Measured on a Compact PRO FF (firmware 4.18.2.0) on a Pixel 8 Pro (Android 16), 2.3.4:

- With the default patches of 0.9.0 and 0.10.0, 10 of 14 relaunches a second after a force-stop came
  up stuck.
- The stock app's code (only the opt-in `debug_log` added) behaved the same: 4 of 6.
- In each stuck start, the first frame's first 256 words were missing and the chunk ended in 256
  words of zeros.  Chunks 1–12 were byte for byte those of a good start.  This was found by logging
  the first frames' header words and saving the first 12 raw frames.

## The patch

The camera library opens the camera in one place: `openDevice()`, then
`claimInterface(interface, true)`.  That call goes through `seekpatch.Relaunch.claimInterface`, which,
once the interface is claimed, sets it again (`UsbDeviceConnection.setInterface`).  Linux then:

- resets the phone's toggles for the interface's endpoints;
- sends SET_INTERFACE, which resets the camera's toggles (USB 2.0 § 9.1.1.5).  A camera that refuses
  it gets CLEAR_FEATURE(ENDPOINT_HALT) on each endpoint, which resets them too (§ 9.4.5).

This happens before the first command, so both ends start at DATA0.  The log says
`relaunch_fix: interface 0 set again, packet numbering starts over`.

With the patch, 30 of 30 relaunches on the same phone started with the picture and a whole first
frame:

- 10 relaunches a second after a force-stop;
- 20 relaunches with 0–2 s waits after sessions of 4–12 s.

Only the Compact PRO FF has run with it.  The Compact uses the same library and opening code, so
the patch applies to it as well, but it is untested.
