# `shutter` — a button that stops the camera's automatic shutter

**Stock:** the camera closes its shutter by itself to recalibrate (a flat-field correction), every
few seconds: the Compact about every 5 s, more often just after connecting.  Each time it clicks,
the picture freezes for 0.44 s and comes back slightly different, and the readings jump a little.
There is no setting for it.
**Patched:** a **Shutter auto** button floats below the top bar, on the right (below *Lock range*).
Tap it and it reads **Shutter off**: no more clicks, freezes or jumps.  Tap again and the automatic
shutter is back; the camera shutters right away, its next calibration being overdue.

- **The price:** without the shutter nothing corrects the sensor's drift.  As the camera warms the
  picture slowly gets noisier and blotchier and the readings wander, faster in the first minutes
  after connecting.  Turn it off for a recording or a measurement that a click would spoil, not for
  good.
- **How long it lasts:** until the app is closed or the button is tapped.  While it is off, a
  reconnected camera (unplugged and plugged in again, which resets it) is turned off again.  A
  camera the app left off (the app was closed with the camera plugged in) is turned back on when it
  next connects.
- **What it doesn't do:** it does not trigger a shutter on demand, and does not change the shutter's
  schedule.  Nothing is written to the camera's flash: unplugging always brings the stock behaviour
  back.

A long press explains the button.

## How it works

The camera's firmware takes vendor requests over USB, one handler per request code.  Request 55
(named *ToggleShutter* in the firmware, *peripheral control* in Seek's later SDK) takes two
little-endian 16-bit words, an address and a value.  For address 255, the shutter, read in the
firmware of the Seek Compact, version 1.3.0.0:

| value | effect |
|---|---|
| 253 | sets a flag in RAM that the automatic shutter checks before each calibration: **suspend** |
| 252 | clears it: **resume** |
| 254, 255 | drive the shutter motor to one of its states directly (refused while the sensor is in some run states) |
| 250, 251 | set the shutter's drive level, as request 56 (*SetShutterPolarity*) does |

Any other value is refused; other addresses are ignored.  The automatic shutter counts frames and,
when the flag is clear and the count reaches the current step of its schedule (frequent at first,
rarer later), runs a calibration and starts counting again.  The count goes on while the flag is
set, so after a resume the next check finds the calibration overdue and runs it (the count is
16-bit: after a very long time off it may have wrapped, and the calibration then waits its turn).
Seek's SDK 4.x sends the same two values to suspend and resume its cameras' shutters.  The Android
app never sends request 55.

The patch sends `bmRequestType 0x41, bRequest 55, wValue 0, wIndex 0` with `FF 00 FD 00` (off) or
`FF 00 FC 00` (on), on the app's own connection, on the thread that asks the camera for each frame,
just before it does: never in the middle of one of the app's requests.  The motor values are not
used: one of them alone could leave the shutter closed.

The patch adds:

| where | what |
|---|---|
| the camera screen, after `setContentView` | `seekpatch.Shutter.attach`: the button, in the frame layout that holds the top bar, on the right, below *Lock range* |
| the method that asks the camera for a frame (`controlTransfer` with request `0x53`) | `Shutter.transfer(connection)`, at its top: sends a tap's command, and notices a new connection |

Whether the camera ran the command is known only from the transfer: if the camera refuses it, the
button stays as it was and says so.

### In the firmware

In `SUBI_LPC43XX_LPCOpen_1.3.0.0` (file offsets of the decrypted image): the request table is at
`0xb42c`, 16-byte entries of name, IN handler, OUT handler and allowed states, from request 53 on;
entry 55 has only an OUT handler and is allowed in both the sleep and run states.  The handler is at
`0x30c0` (the table's pointers run 0x368 bytes ahead of this image's layout, uniformly: 25 of the
30 handlers land on a function entry with that shift); the suspend flag it writes (RAM `0x10002cea`)
is read in one place, the schedule check at `0x61e6`, and written nowhere else.

## On the phone

2.3.4 on a Pixel 8 Pro with a Seek Compact (firmware 1.3.0.0), the live view's frame times read from
SurfaceFlinger, a few minutes after connecting:

| | freezes | frame rate |
|---|---|---|
| automatic (stock) | 9 in 45 s, 0.43 – 0.45 s each, every 5.2 s | 28.6 fps |
| **Shutter off** | **none in 60.8 s** | 31.0 fps |
| on again | the first 70 ms after the command, then every 5.2 s | 28.6 fps |

The app closed while the shutter was off and started again: the camera was resumed as it connected
and its freezes came back (every 3.1 s at first: the reconnect restarts the camera's schedule).

## Versions

The button and its hook go into every release, 1.9.1 – 2.3.4: the frame request looks the same in
all of them.  The command's effect depends on the camera's firmware, not on the app: read in the
Compact's 1.3.0.0.  The Compact's 4.x firmware and the Compact Pro's have not been read or run; if
one refuses the request, the button says so.

Sources: [`helpers/java/seekpatch/Shutter.java`](../helpers/java/seekpatch/Shutter.java).
