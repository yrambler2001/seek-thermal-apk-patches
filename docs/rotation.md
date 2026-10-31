# `rotation` — the thermal picture turned or mirrored

**Stock:** the picture is always the way the camera sees it: upright with the camera plugged into
the phone's port, upside down when the phone is (the app turns it), with no setting for anything
else.
**Patched:** *Settings → Image & Video* has two lists, both off by default:

| setting | choices |
|---|---|
| *Image rotation* | *Off*, *90° clockwise*, *180°*, *270° clockwise* |
| *Mirroring* | *Off*, *Mirror horizontally (left ↔ right)*, *Mirror vertically (top ↔ bottom)*, *Mirror horizontally and vertically* |

They are for a camera that does not sit in the phone's port the usual way: on an extension cable
or a mount, turned on its side, or facing you.  The mirroring comes after the turn, both as seen on
the screen.  (*Mirror horizontally and vertically* looks the same as a turn by 180°.)

**Only the thermal picture turns.**  What the app draws over it stays where it is and upright:

- the hottest and coldest markers (*High/Low* mode) and the spot (*Spot*), with their temperatures.
  Each marker moves with its point of the picture and its text stays readable;
- the temperature bar (*Show Temperature Bar*), on the left, full height;
- the date, camera name and frame-rate box, and the watermark.

A picture turned by 90° or 270° is 4:3 lying on its side and no longer fits the portrait frame.
It is shrunk to fit the frame's width (to 3/4), with black above and below; nothing of it is cut
off.  The live view, photos and videos all look the same, and the 1× copy of `photo_1x` is turned
too (at its own size: 240×320 turned by 90° is 320×240).  The radiometric TIFF of *Store All
Thermal Data* stays as the sensor gives it: it is data, not a picture.

In 16:9 (*Settings → Aspect Ratio*) the app crops the 4:3 picture to fill a 16:9 view.  The patch
turns the whole picture and the app's crop comes after, as without the patch.  At 90° and 270°
that crop takes 12 % off each side of the turned picture.  In Thermal+ the phone camera's picture
does not turn: the thermal picture lines up with it only if the camera is turned the same way.

## How

The app draws the live view in one shader.  The thermal texture and an overlay texture share one
texture coordinate: the overlay holds the markers, the bar and the text, drawn on a 1280×960 canvas
every frame.  The app turns that coordinate itself, by 180° when the phone is upside down.  The
patch:

| where | what |
|---|---|
| vertex shader | a second coordinate, `thermalCoord`, for the thermal texture only: the app's, through `uniform mat2 thermalTurn` (frame → picture minus the identity, so that zero, the uniform's initial value, changes nothing) |
| fragment shaders | the thermal texture sampled at `thermalCoord`, and black where that leaves the texture.  The app's own coordinate, which the overlay and Thermal+'s split line use, is left alone |
| before `glDrawArrays` | `seekpatch.Rotation.uniform()` sets `thermalTurn` from the settings.  The video encoder draws with the same shader, so videos follow |
| the marker method | the method that draws a marker and its temperature at (x, y) moves x, y first: to where that point of the picture is now |
| the photo method | around each draw of the frame onto the photo canvas, the canvas is cleared to black and turned the same way.  In 16:9 the app draws a band of the frame; the patch draws the whole frame and lets the canvas crop it, as the live view does |
| `photo_1x` | `seekpatch.Photo1x` finds `seekpatch.Rotation` by name and turns its copy before turning it upright |

The turn is worked out in the frame's own shape (4:3, the sensor's long side along the screen's
height): one 2×2 matrix for the shader and its inverse for the markers and the photo.  With both
settings off the markers and the photo are drawn exactly as stock.

## On the phone

Pixel 8 Pro, Android 16, Seek Compact PRO FF, 2.3.4:

- the lists in *Image & Video*, and the picture follows a choice as soon as the camera screen is
  back;
- 90° turns the picture clockwise, 270° counterclockwise, 180° upside down; at 90° and 270° it
  fits the width with black above and below;
- each mirroring at 0°, and 90° with *Mirror horizontally* and with *Mirror vertically*: left and
  right, top and bottom swap as named;
- *High/Low*: the hottest and coldest markers stay on their spots in every combination, their text
  upright; the temperature bar stays on the left;
- a photo (with its EXIF turn applied) and a video (HEVC 960×1280) look like the live view, black
  bars and markers included; the 1× copy is turned the same way;
- 16:9: the live view and a photo, turned 90°, match.

Thermal+ was not tried.

Versions: 2.0 – 2.3.4 (the settings screen; 1.9.x has none and saves photos differently).
Sources: [`helpers/java/seekpatch/Rotation.java`](../helpers/java/seekpatch/Rotation.java),
[`RotationSettings.java`](../helpers/java/seekpatch/RotationSettings.java),
[`src/seekpatch/patches/rotation.py`](../src/seekpatch/patches/rotation.py).
