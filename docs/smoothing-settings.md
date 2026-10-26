# `smoothing_settings` — a switch for each of Seek's filters

**Stock:** *Settings → Image & Video* has one *Image smoothing* switch.  It picks between two
presets of the image library's filters, and *off* is the smoother picture (see
[below](#what-the-library-does-with-image-smoothing)).
**Patched:** in its place, one switch per filter:

| switch | default | what it does |
|---|---|---|
| **Default temporal smoothing** | on | Seek's filter (`alpf`): averages each pixel over recent frames |
| **Default spatial smoothing (3×3)** | off | Seek's filter (`aslpf`): blurs each pixel with its neighbours |
| **Default pattern correction** | on | Seek's filter (`sbnuc`): learns and removes the sensor's fixed pattern |
| **Smart smoothing** | off | seek-thermal-apk-patches' filter: follows the camera's motion; replaces temporal smoothing |
| **Stripe correction** | on | part of Smart smoothing: removes column stripes |
| **Left-edge levelling** | on | part of Smart smoothing: levels the bright strip at the left edge |

<img alt="Settings, Image &amp; Video: the switches and lists seek-thermal-apk-patches adds, at their defaults" src="images/image-video-settings.avif" width="336" align="right">

"Default" marks Seek's own algorithms.  The defaults are the stock app with *Image smoothing* on, so
nothing changes until a switch is touched.  The last three appear only when
[`smart_smoothing`](smart-smoothing.md) is in the app too (2.2.3 – 2.3.4).  No switch is greyed
out, because the app's switch class draws a disabled *on* much like *off*: *Default temporal
smoothing* has no effect while Smart smoothing is on (Smart smoothing replaces it, and its summary
says so), and *Stripe correction* and *Left-edge levelling* only act while it is on.  The *Smart smoothing* switch
and the button at the top left of the camera screen are one setting: either moves the other.
Changes apply from the next frame.  The old *Image smoothing* switch is hidden.  Below them come the settings of
[`flat_field`](flat-field.md#setting), [`sharp_scaling`](sharp-scaling.md#settings),
[`photo_1x`](photo-1x.md) and [`video_quality`](video-quality.md#settings).

## Temporal and spatial smoothing

The two noise filters in the camera's image library (libseekip).  They run before the colours are
applied, so they shape the temperature readings as well as the picture.

- *Temporal* smoothing (`alpf`) averages each pixel over time.  It compares the pixel with its
  previous output.  A difference *d* below a threshold *T*, set from the camera's factory
  sensitivity, shows only a fraction *d/T* of itself: noise barely gets through, while a change of
  *T* or more shows at once.  The result becomes the history for the next frame, so a small real
  change creeps in over several frames.  The picture is calm, but faint moving warm things leave
  trails and small temperature changes show late.
- *Spatial* smoothing (`aslpf`) averages each pixel with its neighbours, one frame at a time.  Every
  pixel becomes the mean of its 3 × 3 neighbourhood unless strong slopes around it mark an edge.
  Noise in flat areas drops by up to 3×, but detail too faint to count as an edge is blurred: fine
  texture, thin wires.  The edge test compares only the top-right side of a pixel with the
  bottom-left side, so an edge running exactly from bottom-left to top-right is not seen, and it
  is blurred too.

| | temporal | spatial | detail kept |
|---|---|---|---|
| stock, "Image smoothing" on | on | off | 14.1 % |
| stock, "Image smoothing" off | on | **on** | 10.6 % |

That is why stock *off* looks softer than *on*: it adds the spatial blur and keeps the temporal
one.  *Detail kept* is the per-pixel structure left in the recovered sensor frame (the standard
deviation of the frame minus a 1-pixel blur), relative to the scene's contrast; see
[measuring.md](measuring.md).  Scaling does not change it (on + `sharp_scaling` measures 13.4 %);
filtering does.

## What the library does with "Image smoothing"

Before every frame the app sends feature 900 with the switch's value.  In the image library
(libseekip, `seekip_setfeature` case 900) that value only chooses the first filter's stage mask:

| 900 | mask | stages |
|---|---|---|
| 1 (on) | `0x86` | sbnuc `0x2` + alpf `0x4` + gradient `0x80` |
| 0 (off) | `0x1C4` (`0xC4` on 1401 sensors) | alpf + peak limiting `0x40` + gradient + aslpf `0x100` |

So *off* swaps the pattern correction for a blur, and the temporal filter runs in both positions.
Seek's iOS app has the same mapping.

The value is also stored, but only read back by the matching *get* call.  The rest of case 900
does the same in both positions: per-model defaults for some OEM cores (filter and gradient-stage
features, a different mask for the 2179 / 2497X families), and for mosaic cores it moves the
gradient stage to the second filter.  On the Compact the mask read back is exactly `0x86`: none of
those applies to it.

The first filter runs before the temperatures are computed: raw frame → first filter → spot, min
and max temperatures → second filter → colours.  So every one of these switches changes the
readings as well as the picture.  Temporal smoothing makes spot readings steadier and slower,
spatial smoothing averages each reading with its neighbours, and pattern correction removes the
sensor's fixed pattern from both.

## The patch

Right after the app's feature-900 call, `seekpatch.Filters.frame(handle, sent)`:

1. makes the *on* preset the base: if the app sent 0 (the hidden switch may still be off, from an
   older seek-thermal-apk-patches build or from before), it sends 900 = 1 again;
2. sends a stage feature for each switch that is away from its default:

| switch away from its default | feature | mask bit |
|---|---|---|
| temporal smoothing off | 102 = 0 | clears `0x004` |
| spatial smoothing on | 100 = 1 | sets `0x100` |
| pattern correction off | 106 = 0 | clears `0x002` |

At the defaults nothing is sent, and the mask is stock `0x86`.  The result does not depend on the
hidden switch.  The features go through the app's own `seekIPsetFeature`, with buffers allocated
once.  When the combination changes, or a new camera connection starts, the helper reads the mask
back (feature 132) and logs it:

```
$ adb logcat -s seek-thermal-apk-patches
smoothing_settings: first-filter mask 0x86: temporal on, spatial off, pattern correction on
smoothing_settings: first-filter mask 0x82: temporal off, spatial off, pattern correction on
smoothing_settings: first-filter mask 0x184: temporal on, spatial on, pattern correction off
```

While Smart smoothing is on, the mask still shows `alpf`.  Smart smoothing's hook clears it from
the first filter's flags at the moment of the call (see [smart-smoothing.md](smart-smoothing.md)),
and the log line says so.

Peak limiting, the remaining stage of the old *off* preset, gets no switch: the *on* base does not
run it.

### The settings screen

The Image & Video fragment is found by behaviour: the one `PreferenceFragment` that names
`"use_smoothing"` (it logs the switch's changes) and inflates its preferences in `onCreate`.  Right
after its `addPreferencesFromResource`, `seekpatch.Settings.screen` hides the old switch and appends
the new ones.  The old switch is the last item of the screen in every release, so they take its
place.  They are instances of the app's own switch class, the old switch's class, so they look like
the rest of the screen.  That class colors only its title (white); a switch's summary takes the
theme's color, which on Android 7 (a Redmi 4X) is dark on the screen's black, so `Settings` colors
our summaries itself, in the light grey (`#cccccc`) of the app's own list summaries.  The screen's list runs on under the navigation bar, which the stock screen,
with five items, never reached; `Settings` pads the list's end by the bar's height, so the last item
scrolls clear of it.  The settings screens have no theme, so on Android 15+ (the app targets SDK 35
and is drawn edge to edge) the system gives them a light navigation bar, with the white text running
under it; `seekpatch.Screens` makes that bar black, with a light handle, whenever a settings screen
resumes.  Titles and summaries are English strings in the code.  No resource is read
or added, so this works with `apktool d -r` (the default) as well as with `--side-by-side`.

The values live in a preferences file of seek-thermal-apk-patches' own (`seekpatch`), not in the app's settings:

| key | default |
|---|---|
| `temporal_smoothing`, `spatial_smoothing`, `pattern_correction` | on, off, on |
| `smart_smoothing`, `smart_stripes`, `smart_left_edge` | off, on, on (`smart_smoothing`'s own keys) |

`seekpatch.Settings.attach`, in the camera screen's `onCreate`, loads them before the first frame
and follows every change with a listener.  The per-frame code reads cached values; it never reads
the file.

The same two hooks carry the settings of [`flat_field`](flat-field.md),
[`sharp_scaling`](sharp-scaling.md), [`photo_1x`](photo-1x.md) and [`video_quality`](video-quality.md);
the first of those patches to be applied adds them (`patches/settings.py`).

### The old switch elsewhere

The *Image smoothing* switch also appears as an item of a legacy `ImagePreference`, in
`res/xml/pref_settings.xml`.  In 2.2.0 – 2.2.2 only a `SettingsActivity` loads that file, and
nothing starts that activity: it is declared but not exported, and no code names it.  From 2.2.3
on, nothing loads the file at all.  The item is never on screen, so the patch leaves it alone.

## Versions

2.2.0 – 2.3.4, the releases whose image library has been checked to handle feature 900 and the stage
features this way (libseekip 2.10.5.0 in 2.2.2, 2.11.3.2 in 2.2.3 – 2.3.4; 2.2.0 and 2.2.1 carry
the same preset code); 2.1.x ships an older library whose feature 900 is different, so the patch
refuses apps older than 2.2.0 (versionCode 260).  Up to 2.3.0 the app passes the switch as
`flag ? 1 : 0`, compiled to a small branch; 2.3.4 passes the boolean directly; both shapes are
matched.  The settings fragment exists in this shape from 2.0 on.  The Smart smoothing switches need `smart_smoothing`, which starts at 2.2.3.

Run on a Pixel 8 Pro with a Seek Compact, app 2.3.4 side by side: the switches and their defaults,
the hidden old switch, the button following the switch and back, the values after a restart and
after an update in place, and the logged mask of each combination.  The live view stayed at
25–26 fps with each one (`tools/fps.sh`).  The screenshot is of the current build, with no switch
greyed out.
