# `photo_1x` — the sensor's own pixels, next to each photo

**Stock:** a photo is the colorized frame scaled up to 1280×960, with the overlays (palette bar,
temperatures, spot marker) drawn on top.
**Patched:** with *Settings → Image & Video → Also save a 1x PNG* on (it is off by default), the
same photo plus the frame at the sensor's resolution — 206×156 on a Compact, 320×240 on a Compact
Pro — as a lossless PNG without overlays, turned upright.

| `Pictures/Seek Thermal/img_thermal_1792780046753.png` | `Pictures/Seek Thermal/img_1x_1792780046753.png` |
|---|---|
| 1280×960 (EXIF: rotate 90°), overlays, ~0.6 MB | 156×206, no overlays, ~60 KB |

![The saved photo, shown upright, and its 1× copy enlarged with nearest neighbour](images/photo-1x.avif)

<sub>Left: the photo (with `png_photos` and `sharp_scaling`).  Right: the 1× copy, each sensor pixel
drawn as a block.  Seek Compact, Iron palette.</sub>

It goes **next to the photo**, in the app's own folder, under the photo's name with `_thermal`
turned into `_1x` (Thermal+ photos: `img_tp_thermal_…` → `img_tp_1x_…`).  Seek's in-app gallery
lists only files whose path matches `%Seek Thermal/%_thermal%`, so it does not show the copy; Google
Photos and other galleries show both in the *Seek Thermal* album.  Deleting a photo in Seek's
gallery does not delete its 1× copy.  (Until 0.3.0 the copies went to a separate folder,
`Pictures/Seek Thermal 1x/`, under the photo's own name; those stay where they are.)

## How

The photo method receives the frame as a sensor-sized `Bitmap` before it draws it, scaled, into the
photo canvas.  The patch hands that bitmap and the camera's `Context` to `seekpatch.Photo1x` at the
start of the method, and when the method that writes the EXIF tags and copies the file to its final
name returns, `Photo1x.saved(final file, orientation)` writes the PNG.  The orientation is the
value the app puts in the photo's EXIF; the PNG's pixels are rotated to match, because PNG viewers
ignore EXIF orientation.

Thermal+ photos store the thermal frame.  In 16:9 mode the photo is cropped; the 1× copy keeps the
whole frame.

The switch is `seekpatch.PhotoSettings`; it sets `Photo1x.enabled`, which `capture` checks.  Where a
release has no settings screen for it, `enabled` stays on and every photo gets its copy, as in
0.3.0.  On the Pixel (2.3.4): off, a photo got no copy; on, the next one got its 156×206 PNG, as
`img_1x_…` next to it, and the gallery's query returned the photo alone.

Versions: 2.1.1 and newer.  Sources: [`helpers/java/seekpatch/Photo1x.java`](../helpers/java/seekpatch/Photo1x.java),
[`PhotoSettings.java`](../helpers/java/seekpatch/PhotoSettings.java).
