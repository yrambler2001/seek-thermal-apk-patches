# Measuring

Everything in the README and these pages can be repeated with a phone, `adb` and the tools in
[`tools/`](../tools).

## Getting adb while the camera is plugged in

The camera takes the phone's USB port, so use Wireless debugging (Developer options), or once over
USB: `adb tcpip 5555`, then `adb connect <phone-ip>:5555`.

## Frames on screen

```sh
tools/fps.sh com.tyriansystems.SeekThermal 10            # stock
tools/fps.sh com.tyriansystems.SeekThermal.patched 10    # a --side-by-side build
```

It uses SurfaceFlinger's timestats for the live view's `SurfaceView` layer: frames presented, and
frames the display dropped.  No root and no app changes needed.  With `debug_log` patched in it also
averages the app's `DAQ: fps` lines — the rate the camera delivers.

The phone camera's configured rate: `adb shell dumpsys media.camera | grep "Preview FPS range"`.

## Upscaling kernel

```sh
pip install numpy pillow
adb exec-out screencap -p > live.png
python3 tools/measure_kernel.py live.png --crop 0,594,1008,1938     # the live view's box on the screenshot
python3 tools/measure_kernel.py photo.jpg                          # a saved photo is the whole image
```

It prints the fitted texel grid, the interpolation weights per sub-pixel position (with the bilinear
values beside them), and the "texel detail" of the recovered sensor frame.  Find the live view's box
on your screenshot first (the Pixel 8 Pro's is `0,594,1008,1938`).  `--rows` and `--cols` keep the
app's overlays — palette bar on the left, spot readout in the middle — out of the measurement.

The README's chart is drawn from [`docs/data/kernels.json`](data/kernels.json) by
`tools/kernel_chart.py`.

## CPU

```sh
adb shell top -H -b -d 5 -n 2 -p $(adb shell pidof com.tyriansystems.SeekThermal) -o TID,%CPU,CMD
```

`ThermalPlusRend…` is the GL render thread.

## The numbers in this repo

Pixel 8 Pro, Android 16; Seek Compact, firmware 1.3.0.0; Seek Thermal 2.3.4; Iron palette; the
camera looking at itself in a mirror.  The iOS reference is a photo from Seek Thermal for iOS 2.2.8.0
(image library 2.10.5.0) with a Compact on the same firmware.
