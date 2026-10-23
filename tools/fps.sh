#!/bin/sh
# fps.sh [package] [seconds] -- frames per second a Seek Thermal build puts on screen.
#
#   tools/fps.sh                                   # the store app, 10 s
#   tools/fps.sh com.tyriansystems.SeekThermal.patched 15
#
# Uses SurfaceFlinger's timestats for the live view's SurfaceView layer (no root, any app).  With
# the debug_log patch in, it also averages the app's own "DAQ: fps" lines: the camera's rate.
# Start the live view first; adb must see the phone (wireless debugging if the camera is plugged in).
set -e
pkg=${1:-com.tyriansystems.SeekThermal}
secs=${2:-10}
adb logcat -c 2>/dev/null || true
adb shell dumpsys SurfaceFlinger --timestats -clear -enable >/dev/null
sleep "$secs"
stats=$(adb shell dumpsys SurfaceFlinger --timestats -dump)
adb shell dumpsys SurfaceFlinger --timestats -disable >/dev/null
echo "$stats" | awk -v pkg="SurfaceView[$pkg/" -v secs="$secs" '
	/layerName = / { mine = index($0, pkg) > 0 }
	mine && /totalFrames = / { frames += $3 }
	mine && /droppedFrames = / { dropped += $3 }
	END {
		if (frames == 0) { print "no frames from " pkg " -- is its live view on screen?"; exit 1 }
		printf "on screen: %.1f fps (%d frames in %d s, %d dropped by the display)\n", frames / secs, frames, secs, dropped
	}'
adb logcat -d -s Seekware:D 2>/dev/null | awk '/DAQ: fps: / { s += $NF; n++ } END { if (n) printf "camera:    %.1f fps (app DAQ log, %d samples)\n", s / n, n }'
