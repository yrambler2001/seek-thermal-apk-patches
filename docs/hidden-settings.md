# `hidden_settings` — the hidden switches, always in Settings

**Stock:** Settings has five more switches than it shows.  They appear after tapping *About →
Image Processing Software* five times, and disappear after five more taps.
**Patched:** they are always there:

| switch | what it does |
|---|---|
| *Show Frame Rate* | writes the thermal frame rate in the corner of the live view (*27.9 Hz*); see [`fps_readout`](fps-readout.md) |
| *Save Uncompressed* | photos as PNG instead of JPEG; shown only before Android 11 when [`png_photos`](png-photos.md) is applied, which turns it on for good from Android 11 |
| *Set Simulation Mode* | a simulated Compact: the live view runs without a camera |
| *Disable Registration* | read by the camera registration of the older releases (2.2.3 and before); 2.3.4 has the switch but nothing reads it |
| *Use Staging Server* | the same: registration with Seek's test server in the older releases; nothing reads it in 2.3.4 |

The five taps still flip the stored flags, which no longer matter.

## How it works

The settings screen removes each of these switches, when it builds the list, unless its "allowed"
preference is true: `lossless_comp_allowed_key`, `sim_mode_allowed_key`,
`export_frame_rate_allowed_key`, `allow_reg_optout_key`, `staging_registration_allowed_key`.  The
five taps toggle all five.  Each is read by a small static method, `getBoolean(key, false)`, and
nothing else reads them.  The patch has each of those readers return true.  With `png_photos`,
*Save Uncompressed*'s reader returns `SDK_INT < 30` instead, so the switch is not shown where it
would do nothing.

| where | what |
|---|---|
| the static `(Context)Z` reader of each allowed-key | returns true (Save Uncompressed with `png_photos`: true before Android 11) |

## Versions

2.0 – 2.3.4 have all five switches; 1.9.5 has four (no *Show Frame Rate*), 1.9.3 – 1.9.4 only
*Disable Registration*; the patch shows the ones the app has.  1.9.1 – 1.9.2 hide nothing.

On a phone (2.3.4, Pixel 8 Pro, Android 16, with `png_photos`): Settings lists *Set Simulation
Mode*, *Show Frame Rate*, *Disable Registration* and *Use Staging Server*, with the stored flags
both ways (flipped by the five taps, which still show the app's version toast); *Save
Uncompressed* is not shown, as `png_photos` has it on.
