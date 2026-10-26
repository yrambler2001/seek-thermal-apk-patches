# `default_unit` — start in Celsius

**Stock:** until a unit is picked, the app shows Celsius, but Fahrenheit on a phone set to English
(United States).
**Patched:** it starts in Celsius everywhere.  A unit picked in *Settings → Preferences →
Temperature Units* is stored, as before, and stays: the patch only changes what an app with no
stored unit starts with (a new install, or cleared app data).

## How

The app stores the unit in its preferences as `units`: 0 Fahrenheit, 1 Celsius, 2 Kelvin.  Until
one is stored it takes the integer resource `default_unit`, which is 1 in `values/integers.xml`
and 0 in `values-en-rUS/integers.xml`, and its first read stores that default.  The same resource
also picks defaults that follow the unit, such as a threshold of 27 °C rather than 80 °F.

The patch finds the resource from the `units` read: the id that goes into its
`Resources.getInteger()` call, a constant up to 2.3.0 and a field of the obfuscated R class in
2.3.4.  Then every `getInteger()` of that id, in the whole app, calls `seekpatch.Units.celsius`
instead, which answers 1.  Resources are not touched, so the default build (`apktool d -r`)
carries them over byte for byte.

Versions: 1.9.1 – 2.3.4.  Not seen on a phone: both test phones have a unit stored, which the
patch leaves alone.  A phone that started the app before (stock, or patched without this patch)
has its unit stored by then, Fahrenheit on an English (US) phone: pick Celsius once in the
settings.
