package seekpatch;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;

/**
 * seek-thermal-apk-patches lock_range: a "Lock range" button that holds the colors where they are, so a hotter or
 * colder object entering the scene no longer recolors everything else.
 *
 * <p>The app's image comes out of libseekip's contrast stage, which builds a new curve from raw sensor
 * value to palette entry on every frame, from the frame's histogram.  While locked, the native library
 * libseekpatch_lock.so keeps the stage from rebuilding it: the image does not change at the tap, and
 * each raw value keeps its color afterwards.  The temperature bar keeps the minimum and maximum it
 * showed at the tap ({@link #scene}, {@link #bar}, {@link #low}, {@link #high}).  A second tap unlocks;
 * so does a camera reconnect.  The lock lasts until the app is closed.  See docs/lock-range.md.
 */
public final class Lock {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String LIBRARY = "seekpatch_lock";
    private static final long STALE_MS = 1000;
    private static final String LABEL = "Lock range";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final int NONE = 0;
    private static final int LOCK = 1;
    private static final int UNLOCK = 2;

    private static volatile boolean locked;
    private static volatile int request;  // main thread -> camera thread
    private static volatile float low;    // the bar's minimum at the tap, °C
    private static volatile float high;   // its maximum
    private static WeakReference<TextView> button = new WeakReference<>(null);

    // scene minimum / maximum (°C), written by the camera thread
    private static volatile float sceneLow;
    private static volatile float sceneHigh;
    private static volatile long sceneAt;

    // camera thread
    private static boolean installed;
    private static boolean failed;

    private Lock() {
    }

    /** After the activity's setContentView: the button floats below the top bar, right side, first. */
    public static void attach(Activity a) {
        try {
            TextView b = Floating.button(a, "Keeps the colors as they are now, whatever enters the view; tap again for automatic",
                    new View.OnClickListener() {
                        @Override
                        public void onClick(View v) {
                            tap((TextView) v);
                        }
                    });
            if (Floating.place(a, b, true, 10)) {
                button = new WeakReference<>(b);
                show(b);
            }
        } catch (Throwable t) {
            Log.w(TAG, "lock_range: no button", t);
        }
    }

    private static void tap(TextView b) {
        if (failed) {
            Toast.makeText(b.getContext(), "Lock range is not available here", Toast.LENGTH_SHORT).show();
        } else if (locked) {
            request = UNLOCK;
        } else if (SystemClock.uptimeMillis() - sceneAt > STALE_MS) {
            Toast.makeText(b.getContext(), "No camera image", Toast.LENGTH_SHORT).show();
        } else {
            low = sceneLow;
            high = sceneHigh;
            request = LOCK;
        }
    }

    private static void show(TextView b) {
        if (locked) {
            int unit = Floating.unit(b.getContext());
            // whole degrees as the bar writes them: truncated
            b.setText("Locked " + (int) Floating.toUnit(low, unit) + "–" + (int) Floating.toUnit(high, unit) + Floating.symbol(unit));
        } else {
            b.setText(LABEL);
        }
        Floating.style(b, locked);
    }

    /** Camera thread, after every frame: the scene's minimum and maximum temperature (°C). */
    public static void scene(float min, float max) {
        if (Float.isNaN(min) || Float.isNaN(max) || Float.isInfinite(min) || Float.isInfinite(max)) {
            return;
        }
        long now = SystemClock.uptimeMillis();
        if (now - sceneAt > STALE_MS) {
            sceneLow = min;
            sceneHigh = max;
        } else {  // the extremes are single pixels: smooth them, 1/8 a frame
            sceneLow += (min - sceneLow) / 8;
            sceneHigh += (max - sceneHigh) / 8;
        }
        sceneAt = now;
    }

    /** Camera thread, before every frame: a tap's request, and the end of a lock by a reconnect. */
    public static void frame() {
        int r = request;
        if (failed || (r == NONE && !locked)) {
            return;
        }
        try {
            if (!installed) {
                System.loadLibrary(LIBRARY);
                String why = install();
                if (why != null) {
                    unavailable(why);
                    return;
                }
                installed = true;
            }
            request = NONE;
            if (r == LOCK) {
                hold(true);
                locked = true;
                Log.i(TAG, "lock_range: locked; the bar keeps " + low + " - " + high + " °C");
                refresh(null);
            } else if (r == UNLOCK) {
                hold(false);
                locked = false;
                Log.i(TAG, "lock_range: automatic");
                refresh(null);
            } else if (released()) {
                locked = false;
                Log.i(TAG, "lock_range: the camera was reconnected, automatic again");
                refresh("Camera reconnected: the range is automatic again");
            }
        } catch (Throwable t) {
            unavailable(String.valueOf(t));
        }
    }

    private static void unavailable(String why) {
        failed = true;
        locked = false;
        Log.w(TAG, "lock_range: unavailable, " + why);
        refresh("Lock range is not available here");
    }

    private static void refresh(final String message) {
        MAIN.post(new Runnable() {
            @Override
            public void run() {
                TextView b = button.get();
                if (b != null) {
                    show(b);
                    if (message != null) {
                        Toast.makeText(b.getContext(), message, Toast.LENGTH_SHORT).show();
                    }
                }
            }
        });
    }

    /** The temperature bar: whether it writes the span (here, the locked labels) rather than the scene's extremes. */
    public static boolean bar(boolean span) {
        return span || locked;
    }

    /** The temperature bar's span minimum (°C). */
    public static float low(float min) {
        return locked ? low : min;
    }

    /** The temperature bar's span maximum (°C). */
    public static float high(float max) {
        return locked ? high : max;
    }

    /** Hooks the image library; null when done, else why not (nothing was changed). */
    private static native String install();

    /** Holds the contrast curve of the last frame shown, or lets it go. */
    private static native void hold(boolean on);

    /** Whether a reconnect ended the lock since the last call. */
    private static native boolean released();
}
