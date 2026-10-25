# `default_palette` — start in Tyrian

**Stock:** until a palette is picked, the camera starts in *Spectra*.
**Patched:** it starts in *Tyrian*.  A palette picked in the palette bar is stored, as before, and
stays: the patch only changes what an app with no stored palette starts with (a new install, or
cleared app data).

## How

The app stores the chosen palette in its preferences as `color_palette`, an index into a list of
palettes it builds in code:

| index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| palette | White | Black | **Spectra** (stock default) | Prism | **Tyrian** | Iron | Amber | Hi | HiLo | RedHot |

It reads the index with `getInt("color_palette", 2)`.  The patch finds that read and replaces the
default.  The index is not hard-coded: the patch reads where "Tyrian" goes in the list, which is
built with one `aput-object` per name (2.0 – 2.1.x, 2.3.1+) or one `filled-new-array` over the
names (2.2.0 – 2.3.0).

Versions: 2.0 – 2.3.4 (1.9.x has no such list).  Not seen on a phone: the test phone has a palette
stored, which the patch leaves alone.
