# `language` — a Language list in Settings, and the patches' text in every language

**Stock:** the app shows the phone's language, or English when it has none of the phone's
languages, and has no setting for it.
**Patched:** *Settings* starts with *Language*: *System default* (with the language that gives,
e.g. *System default (Русский)*) or any language the app has text in, each named in itself.  The
app switches at once, and the choice stays after a restart.  When the app is not in English the
title also says *(Language)*, so the list can be found again in a language one cannot read.

The list offers the languages of the file that was patched, read from its resources:

| app | languages besides English |
|---|---|
| 1.9.5 – 2.3.4 | German, Spanish, French, Italian, Japanese, Korean, Dutch, Portuguese, Portugal's Portuguese, Russian, Chinese (simplified) |
| 1.9.1 – 1.9.4 | German, Spanish, French, Italian, Dutch, Portuguese (no Settings list: see Versions) |

A download can lack some of them.  The Play Store splits the app by language, and a bundle carries
the language splits its source chose: APKPure's bundles and APK of 2.3.1 – 2.3.4 have no Dutch,
one 2.3.3 bundle has Dutch but no Japanese.  A language the file lacks is not offered.

Portugal's Portuguese has 255 of the app's strings; the others come from its Portuguese, which is
itself mostly European (*câmara*, *ecrã*).  The list names it *Português* and *Português
(Portugal)*.

## The patches' own text

Everything the patches put on the screen — the buttons and their long-press tips, toasts, the
calibration and microphone dialogs, the settings in *Image & Video*, the credit in the side menu —
is translated into every language of Seek's: German, Spanish, French, Italian, Japanese, Korean,
Dutch, Portuguese, Russian and Chinese.  It is in the language of the app's own text, in every
patch, with `language` or without it: the language chosen here, or else the first of the phone's
languages that the app has, as Android picks the app's resources, or else English.  Portugal's
Portuguese gets the Portuguese text, as the app does for the strings it lacks.

The translations are in [`src/seekpatch/strings`](../src/seekpatch/strings), one JSON file per
language: English text → translation.  They were written for this project, following the app's
own translations' terms and form of address, and have not yet been checked by native speakers;
corrections are welcome.

The camera screen's top bar has the Seek logo and the camera's name in its middle, and the *Smart
smoothing* and *Flat field* buttons at its sides.  A longer label (*Плоское поле*) on a narrow
phone would run into the name, so the logo and the name move aside, as far as the other button
leaves room, and only what is still missing comes off the button: its padding first, then its
text, down to 9 sp (`seekpatch.TopBar`, measured at every layout of the bar).  On the Redmi 4X
(360 dp) in Russian the name moves 36 px; in English 14 px, as *Flat field* touched the name
before.  Wider phones keep everything where it was.

The app's own text stays the app's: the few strings Seek never translated (*Starting*, the
Thermal+ alignment tip, the date hint and a camera-permission toast) stay in English.  The
exception is the developer switches Seek left in English (*Save Uncompressed*, *Set Simulation
Mode*, *Disable Registration*, *Use Staging Server*): [`hidden_settings`](hidden-settings.md),
which keeps them on the screen, translates their titles and adds a line under each switch on what
it does.

## How it works

| where | what |
|---|---|
| the Settings screen's `onCreate`, after `addPreferencesFromResource` | `Language.screen`: the list, first (below the spacer in 2.3.4), of the class of the screen's own lists |
| every class that extends one of Android's activity classes | an `attachBaseContext` that passes the context through `Lang.wrap` (or that call at the start of the class's own) |

The Settings screen is the one `PreferenceFragment` that inflates its preferences in `onCreate` and
names `"image_and_video"`, the entry that opens *Image & Video*.  Every activity of the app extends
one of the classes that get `attachBaseContext`, so all of them inherit it: in 2.3.4 `MainActivity`,
`SplashActivity`, `PreferencePage`, `AboutPreferencePage`, `CommunityActivity`, the image viewer's
base class and two library classes; 2.0 – 2.2.x have 25 or 26 (the account screens of those
releases are activities of their own).

The choice is applied by `seekpatch.Lang`:

- **Android 13 and later:** it is the app's language in the system
  (`LocaleManager.setApplicationLocales`).  Android keeps it, recreates the app's screens, and
  gives every context of the app that language; `Lang.wrap` does nothing.
- **Before Android 13:** it is kept in the patches' own preferences file.  `Lang.wrap` gives each
  screen a context that overrides the locale and nothing else, so the rest of the configuration
  (font size, orientation) still follows the phone, also after a rotation.  It also sets the
  default locale: number formats, and the app's own checks for `ru_` and `fr_`, which make its text
  smaller in those languages.  A screen made before the choice changed (the camera screen behind
  Settings) is recreated when it comes back.

A language is applied with its region where the app looks at it: `ru-RU`, `fr-FR`, `de-DE`, …;
Portuguese as `pt-BR` (the app's `values-pt`), Portugal's as `pt-PT`, Chinese as `zh-CN`, English
as `en`.

Android 13's own per-app language page (*Settings → Apps → Seek Thermal → Language*) lists only apps
that declare their languages in their resources.  The patches carry the resources over byte for
byte, so the app is not listed there; the list in the app is the way to choose.

The languages are counted in the app's `resources.arsc` when it is patched (or in `res/` with
`--side-by-side`): a locale is one of the app's when it has at least a quarter as many strings as
the default.  Seek's own translations have 60 – 100 %; the libraries' locales that 1.9.3 carries
have about 10 % (32 of 297).  A split bundle is merged first, so its language splits are counted.  They go into the generated class `seekpatch.Strings` together with
the translations, so the patches' text and the list know which languages the app shows.

## Versions

2.0 – 2.3.4: the Settings screen with its *Image & Video* entry.  1.9.x has another settings
screen, and the patch refuses it; the patches' text there still follows the phone's language.

On a phone (2.3.4, Pixel 8 Pro, Android 16, with a camera attached): the list offers the eleven
languages of the APKPure 2.3.4 file and *System default (English)*.  Choosing *Русский* set the
app's language in the system (`cmd locale get-app-locales`: `[ru-RU]`) although the app declares no
languages; Settings, *Image & Video* with the patches' settings and their lists, the side menu and
its credit, and the camera screen's buttons (*Умное сглаж. выкл*, *Плоское поле*, *Затвор: авто*,
*Закрепить диапазон*, locked: *Закреплён 46–47°C*) came up in Russian, the dialogs' own buttons
too (*Отмена*).  The choice stayed after a force-stop.  Choosing *System default* again cleared
it; the camera screen was recreated each time and its camera came back by itself.

On a Redmi 4X (Android 7.1.2, with the camera), where the patch applies the language itself:
choosing *Русский* recreated Settings in Russian; the camera screen behind it was recreated when
it came back, in Russian, and its camera came back.  The choice stayed after the app was updated
and started again.  *System default (English)* — also in Russian: *Как в системе (English)* —
brought English back the same way.
