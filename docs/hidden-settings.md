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

## A line under each switch

Each switch says what it does, in a grey line under its title, in the app's language like all
the patches' text (see [`language`](language.md#the-patches-own-text)).  The four titles Seek
left in English — *Save Uncompressed*, *Set Simulation Mode*, *Disable Registration*, *Use
Staging Server* — are translated too.  *Store All Thermal Data*, a switch the app always shows,
gets a line as well.

| switch | its line |
|---|---|
| *Save Uncompressed* | Photos as PNG, lossless, instead of JPEG.  Before Android 11 it adds: *Needs Android 11: on older Android the app cannot save them*.  The app writes EXIF into every photo with Android's `ExifInterface`, which can write into a PNG only from Android 11; before that the step fails and the photo stays in the app's cache instead of reaching *Pictures/Seek Thermal* |
| *Set Simulation Mode* | A simulated camera: the camera screen works with no camera attached |
| *Show Frame Rate* | The camera's frame rate in a corner of the image, e.g. 27.9 Hz |
| *Disable Registration* | up to 2.2.3: Seek's test switch for the camera registration (register.thermal.com); from 2.3.0: Does nothing in this version of the app: it no longer registers cameras |
| *Use Staging Server* | up to 2.2.3: Registers the camera on Seek's test server, register-staging.thermal.com; from 2.3.0 the same line as *Disable Registration* |
| *Store All Thermal Data* | from 2.1.1: With each photo, a TIFF file with every pixel's temperature (Span & Level and Full Frame modes, the two mode icons whose photos the app saves it for); no line before 2.1.1 |

Which lines apply comes from the app itself: the registration server's address
(`"https://register.thermal.com"`, up to 2.2.3) and the TIFF's name (`"_thermo_"`, from 2.1.1).
The patch writes what it found into `seekpatch.Hidden`, which fills in the lines once the Settings
screen has its preferences.  That screen exists from 2.0 on; 1.9.x keeps the switches on another
screen, which gets no lines.

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
| the Settings screen's `onCreate`, after `addPreferencesFromResource` (2.0 on) | `seekpatch.Hidden.screen`: the lines under the switches, and the titles in the app's language |

## Versions

2.0 – 2.3.4 have all five switches; 1.9.5 has four (no *Show Frame Rate*), 1.9.3 – 1.9.4 only
*Disable Registration*; the patch shows the ones the app has.  1.9.1 – 1.9.2 hide nothing.

On a phone (2.3.4, Pixel 8 Pro, Android 16, with `png_photos`): Settings lists *Set Simulation
Mode*, *Show Frame Rate*, *Disable Registration* and *Use Staging Server*, with the stored flags
both ways (flipped by the five taps, which still show the app's version toast); *Save
Uncompressed* is not shown, as `png_photos` has it on.

With the lines (2.3.4, 2026-10-30): the Pixel 8 Pro (Android 16) shows a line under *Set
Simulation Mode*, *Show Frame Rate*, the two registration switches (*Does nothing in this
version*) and *Store All Thermal Data*, in English and in Russian.  The Redmi 4X (Android 7.1,
360 dp) also shows *Save Uncompressed* with its Android 11 note, and every Russian title fits on
one line.
