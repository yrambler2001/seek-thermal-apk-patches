# Changelog

## 0.6.0 — 2026-10-25

Your own temperature calibration, and a switch for the camera's automatic shutter.

- `calibration`, in the default set (2.2.3 – 2.3.4): a **k·x+b** button below the top bar, on the
  left.  Enter a gain and an offset (*shown = k × measured + b*, b in the app's unit) and every
  temperature the app shows and saves is corrected: the spot, the minimum and maximum, the
  temperature bar, the radiometric data, and the coloring modes that work in degrees.  It stays set
  until changed.  A third small native library, `libseekpatch_calib.so`, hooks libseekip's
  `thermography_process` and maps its outputs; with no correction set nothing is hooked.
- `shutter`, in the default set (1.9.1 – 2.3.4): a **Shutter** button below *Lock range*.  A tap
  suspends the camera's automatic shutter (no clicks or frozen frames; the picture drifts instead),
  a second tap resumes it and the camera shutters right away.  The command is the camera firmware's
  own shutter request (USB vendor request 55), read in the Compact's firmware 1.3.0.0; it only sets
  a flag in the camera's RAM.
- The floating buttons below the top bar share one helper, `seekpatch.Floating`, which stacks them
  in a column on each side whichever patches are applied; *Lock range* uses it too, unchanged in
  look and place.  `add_helpers` leaves a shared helper another patch already added alone.

## 0.5.0 — 2026-10-25

A Lock range button: the colors stay as they are, whatever enters the view.

- `lock_range`, in the default set (2.2.3 – 2.3.4): a **Lock range** button below the top bar.  A
  tap keeps the image as it is: the image library's contrast stage stops rebuilding its curve (raw
  value → palette entry) every frame, so each temperature keeps its color, and the temperature bar
  keeps the numbers it showed (*Locked 14–19°C*).  A second tap, or a camera reconnect, unlocks.  A
  second small native library, `libseekpatch_lock.so`, hooks libseekip's `create_transfer`.
- The native code that finds and swaps libseekip's PLT slots moved from `smooth_android.c` to
  `plt.c`, shared by both libraries; `smart_smoothing`'s library is rebuilt, same behaviour.

## 0.4.0 — 2026-10-25

Settings in the app for Seek's filters, Smart smoothing, upscaling, the flat field, the 1x PNG and
video quality; Tyrian as the default palette; the 1x copy beside its photo.

- `smoothing_settings`, in the default set: *Settings → Image & Video* gets a switch for each of
  Seek's filters in place of *Image smoothing* — *Default temporal smoothing* (on), *Default spatial
  smoothing (3×3)* (off), *Default pattern correction* (on) — and, with `smart_smoothing`, *Smart
  smoothing* with *Stripe correction* and *Left-edge levelling*.  The defaults are the stock
  picture.  Right after the app's per-frame preset the patch makes the *on* preset the base,
  whatever the hidden old switch says, and sets the three stages from the switches; the mask is
  logged when it changes.  The Smart smoothing switch and the top-left button are one setting
  (2.2.0 – 2.3.4).  No switch is ever greyed out: the app's switch draws a disabled *on* much like
  *off*, so each summary says what depends on what instead.
- `no_smoothing` leaves the default set: it is the opt-in alternative to `smoothing_settings`.  The
  two refuse to combine, `-p` with both is an error, and `--all` leaves `no_smoothing` out.
- `smart_smoothing`: stripe correction and left-edge levelling can be switched at run time (a new
  JNI entry; the native libraries are rebuilt).  The button follows its stored value, so a settings
  switch moves it.
- A setting for `sharp_scaling` (2.0 – 2.3.4): *Upscaling*, one list from soft to blocky — *Smooth*
  (the stock Android bilinear scaling, live view and photos), *Sharp 1.5* to *Sharp 8* (2 = iOS, the
  default) and *Blocky* (square pixels; the photo is drawn unfiltered).  The shader's sharpness is
  now a uniform; at 1 or less it returns the stock sample exactly.
- A setting for `flat_field` (2.2.0 – 2.3.4): *Flat field frames*, how many frames a tap learns
  from — 5, 10, 15, 20, 30, 40 (the default, as before) or 60 — each shown with the share of the
  gradient it learns.  The run's time limit grows with the count (150 ms a frame, at least 5 s).
- `photo_1x` becomes a setting, *Also save a 1x PNG*, **off by default**: 0.3.0 saved the 1× copy
  with every photo.  Where a release has no settings screen for it, it still saves with every photo.
  The copy now goes next to the photo, in the app's own folder, as `img_1x_….png` (Seek's gallery
  skips it), instead of a new `Pictures/Seek Thermal 1x/` folder.
- `default_palette`, in the default set (2.0 – 2.3.4): the camera starts in *Tyrian* instead of
  *Spectra* until a palette is picked; a stored choice stays.
- The settings screens get a black navigation bar: they have no theme, so Android 15+ drew them a
  light one, with the white text running under it.
- The side menu gets a divider and "Patched by yrambler2001 v0.4.0" below *Send Feedback*: the
  version of seek-patch that patched the app, written into it at patch time (`seekpatch.About`).
- A setting for `video_quality` (2.1.2 – 2.3.4): *Video quality*, the QP from 14 to 28 with the size
  of each, used from the next recording.  `--sharpness` and `--video-qp` are now the settings'
  defaults.
- Settings in the app: a shared hook after the Image & Video screen's own preferences and in the
  camera screen's `onCreate` (`patches/settings.py`, `seekpatch.Settings`); the preferences are the
  app's own classes, the values a preferences file of seek-patch's.  The screen's list is padded by
  the navigation bar, which would otherwise cover the last item.  `seekpatch.SeekIP` is shared by
  `flat_field` and `smoothing_settings`.

## 0.3.0 — 2026-10-24

The first public release: a Smart smoothing button, split bundles as input, and a step-by-step
quick start for Windows, macOS and Linux.

- Split bundles as input: `.xapk`, `.apks`, `.apkm`, or any zip of a base apk and its splits (such
  as the files `adb pull` gives for a Play Store install).  They are merged into one apk with
  APKEditor 1.4.9 (fetched on first use, verified by sha256), then patched as before.  This covers
  2.3.1, which APKPure only offers as an `.xapk`.
- `smart_smoothing`: a *Smart smoothing* button at the top left of the camera screen, off by
  default and remembered across restarts.  On, the image library's first filter runs without its
  temporal smoothing (`alpf`), and its output goes through seek-patch's motion-compensated noise
  filter, in place.  The filter follows the camera's motion, averages up to 8 frames per pixel,
  removes column stripes and levels the strip at the screen's left edge; temperatures, photos and
  video get the cleaner frame.  It is a small native library of seek-patch's own
  (`helpers/native`, built reproducibly with `helpers/build_native.py`, committed for arm64-v8a and
  armeabi-v7a) that swaps libseekip's GOT entries for `filter_process` / `filter_process_shutter`,
  after checking the library is one of the four builds it was verified on (2.2.3 – 2.3.4).
- Patches can add native libraries (`SmaliTree.add_native_library`): written to `lib/<abi>/` on
  save, rolled back with the patch, stored uncompressed and page aligned in the apk.
- `mic_prompt`: 2.3.1 – 2.3.4.  2.3.1, now testable, has 2.3.3's microphone check.

## 0.2.0 — 2026-10-23

Photos, videos, the microphone and a flat-field button.  All new patches are in the default set.

- `png_photos`: photos as lossless PNG — the app's hidden *Save Uncompressed* setting, forced on
  (Android 11+; 2.1.2 – 2.3.4).
- `photo_1x`: with every photo, the thermal frame at the sensor's resolution as a PNG in
  `Pictures/Seek Thermal 1x/` (2.1.1 – 2.3.4).
- `video_quality`: HEVC (or H.264, `--video-codec avc`) at the photo's 960×1280, constant QP
  (`--video-qp`, default 18, chosen by measurement), one frame per thermal frame instead of 15 fps,
  keyframes every second, BT.709 tags; stereo 48 kHz AAC at 256 kbit/s (2.1.2 – 2.3.4).
- `mic_prompt`: only starting a video asks for the microphone, and the video starts once answered;
  photos and the gallery no longer need it; a settings / record-without-sound dialog once Android
  stops asking (2.3.3 – 2.3.4).
- `flat_field`: a *Flat field* button in the top bar.  Point at a uniform surface and tap; the
  image library's gradient stage learns the camera's own gradient from the next 40 frames, which it
  otherwise does only from frames that already look flat — never on an unevenly warmed camera
  (2.2.0 – 2.3.4).
- `resume_fix`: the app no longer crashes when it comes back from Android's permission dialog — the
  live view's EGL surface is destroyed on pause (1.9.1 – 2.3.4).
- Java helpers (`helpers/java`) compiled to committed smali by `helpers/build.py` (`--check`: is the
  committed smali up to date).
- `tools/codecs.py`: list the phone's encoders, and score a QP ladder against a reference recording.

## 0.1.0 — 2026-10-23

First release.

- `full_fps`: draw every thermal frame instead of every phone-camera frame (1.9.1 – 2.3.4).
- `sharp_scaling`: iOS-like upscaling in the thermal shader, with the same kernel for saved photos
  (2.0 – 2.3.4).
- `no_smoothing`: the "Image smoothing" switch's off position turns temporal and spatial smoothing
  off (2.2.0 – 2.3.4).
- `debug_log`: the SDK's frame-timing log in logcat (2.0 – 2.3.4).
- `seek-patch list / check / patch / doctor`; `--side-by-side`, `--sharpness`, `--install`.  The default
  patch set skips patches that do not apply to the APK's version; `check` suggests the command line.
- Refuses the base APK of a split install (native code missing) instead of building an app that crashes.
- apktool 3.0.3 and uber-apk-signer 1.3.0 fetched on first use and verified by sha256; zipalign in
  Python (16 KiB page alignment for native libraries); a per-user signing key.
