package seekpatch;

import android.app.Activity;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.RelativeLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * seek-thermal-apk-patches flat_field: a "Flat field" button that has the image library learn the camera's own
 * gradient from a uniform surface.
 *
 * <p>libseekip's gradient stage subtracts a smooth correction map, and learns it only from frames
 * that already look flat: no 16x16 block with detail over one limit, no step between neighbouring
 * blocks over another.  A camera that has warmed unevenly puts a gradient into every frame, never
 * passes, and keeps an empty map.  Feature 30105 makes the stage learn from every frame regardless.
 * A tap sets it until the stage has learned from {@link #updates} frames (40 unless the <i>Flat field
 * frames</i> setting says otherwise, seekpatch.FlatSettings), then clears it, and the stock test
 * takes over again.  {@link #frame} runs on the camera thread before every frame,
 * right after the app has sent its own features.
 */
public final class Flat {
    private static final String TAG = "seek-thermal-apk-patches";
    // Gradient-stage features of the first filter; the second filter's copy is at + 40000.
    private static final int DETAIL_LIMIT = 30100;
    private static final int DETAIL = 30101;
    private static final int STEP_LIMIT = 30102;
    private static final int STEP = 30103;
    private static final int COUNT = 30104;
    private static final int FORCE = 30105;
    private static final int FILTER2 = 40000;
    /** Frames per tap.  The map moves 1/8 of the way per frame: after 40 frames (7/8)^40 = 0.5 % is left. */
    public static volatile int updates = 40;
    private static final long TIMEOUT_MS = 5000;  // at least; 150 ms a frame for long runs on slow cameras
    private static final long NO_CAMERA_MS = 2000;
    private static final String LABEL = "Flat field";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private static final AtomicBoolean requested = new AtomicBoolean();
    private static boolean busy;  // main thread: a tap is being served
    private static int taps;      // main thread
    private static WeakReference<TextView> button = new WeakReference<>(null);

    // camera thread
    private static boolean running;
    private static long runHandle;
    private static int start1;
    private static int start2;  // Integer.MIN_VALUE: the second filter does not answer
    private static int target;  // this run's frames
    private static long deadline;

    private Flat() {
    }

    /** After the activity's setContentView: the button goes into the top bar, right side. */
    public static void attach(Activity a) {
        try {
            View bar = find(a, "main_view_top_panel");
            if (!(bar instanceof RelativeLayout)) {
                Log.w(TAG, "flat_field: no top bar for the button (" + bar + ")");
                return;
            }
            final TextView b = new TextView(a);
            b.setText(Lang.t(LABEL));
            b.setTextColor(0xffffffff);
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            b.setGravity(Gravity.CENTER);
            b.setPadding(dp(a, 12), 0, dp(a, 12), 0);
            GradientDrawable background = new GradientDrawable();
            background.setCornerRadius(dp(a, 14));
            background.setColor(0x33ffffff);
            background.setStroke(dp(a, 1), 0xb3ffffff);
            b.setBackground(background);
            b.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    tap(b);
                }
            });
            b.setOnLongClickListener(new View.OnLongClickListener() {
                @Override
                public boolean onLongClick(View v) {
                    Toast.makeText(v.getContext(), Lang.t("Point the camera at a uniform surface, then tap"), Toast.LENGTH_LONG).show();
                    return true;
                }
            });
            RelativeLayout.LayoutParams lp = new RelativeLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(a, 28));
            lp.addRule(RelativeLayout.ALIGN_PARENT_RIGHT);
            lp.addRule(RelativeLayout.CENTER_VERTICAL);
            lp.rightMargin = dp(a, 12);
            ((RelativeLayout) bar).addView(b, lp);
            TopBar.fit(a, bar, b, true);
            button = new WeakReference<>(b);
        } catch (Throwable t) {
            Log.w(TAG, "flat_field: no button", t);
        }
    }

    private static void tap(TextView b) {
        if (busy) {
            return;
        }
        busy = true;
        final int tap = ++taps;
        b.setText(Lang.t("Hold still…"));
        b.setAlpha(0.6f);
        requested.set(true);
        MAIN.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (requested.compareAndSet(true, false)) {
                    done(Lang.t("No camera image"));
                }
            }
        }, NO_CAMERA_MS);
        MAIN.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (busy && taps == tap) {
                    done(Lang.t("Flat field interrupted, tap again"));  // the frames stopped
                }
            }
        }, NO_CAMERA_MS + timeout(updates) + 1000);
    }

    private static long timeout(int frames) {
        return Math.max(TIMEOUT_MS, frames * 150L + 1000);
    }

    /** Camera thread, before every frame, with the image library's handle. */
    public static void frame(long handle) {
        if (!running && !requested.get()) {
            return;
        }
        try {
            if (requested.compareAndSet(true, false)) {
                start(handle);
            } else if (handle != runHandle) {
                running = false;  // a new connection: its map starts empty, the old handle is gone
                done(Lang.t("Camera reconnected, tap again"));
            } else {
                int learned = Math.max(get(handle, COUNT, 4) - start1,
                        start2 == Integer.MIN_VALUE ? 0 : get(handle, FILTER2 + COUNT, 4) - start2);
                if (learned >= target) {
                    stop(handle, learned);
                    done(Lang.t("Flat field set"));
                } else if (SystemClock.uptimeMillis() > deadline) {
                    stop(handle, learned);
                    done(Lang.t("Flat field interrupted, tap again"));
                }
            }
        } catch (Throwable t) {
            running = false;
            Log.w(TAG, "flat_field: failed", t);
            try {
                set(handle, FORCE, 0);  // this frame's handle is alive
                set(handle, FILTER2 + FORCE, 0);
            } catch (Throwable ignored) {
                // nothing more to undo
            }
            done(Lang.t("Flat field failed"));
        }
    }

    private static void start(long handle) {
        try {
            Log.i(TAG, "flat_field: learning; detail " + get(handle, DETAIL, 2) + " (limit " + get(handle, DETAIL_LIMIT, 2)
                    + "), step " + get(handle, STEP, 2) + " (limit " + get(handle, STEP_LIMIT, 2) + ")");
        } catch (IllegalStateException e) {
            Log.i(TAG, "flat_field: learning (" + e.getMessage() + ")");  // only the log line is lost
        }
        start1 = get(handle, COUNT, 4);
        try {
            start2 = get(handle, FILTER2 + COUNT, 4);
        } catch (IllegalStateException e) {
            start2 = Integer.MIN_VALUE;
        }
        set(handle, FORCE, 1);
        if (start2 != Integer.MIN_VALUE) {
            set(handle, FILTER2 + FORCE, 1);
        }
        running = true;
        runHandle = handle;
        target = updates;
        deadline = SystemClock.uptimeMillis() + timeout(target);
    }

    private static void stop(long handle, int learned) {
        running = false;
        set(handle, FORCE, 0);
        if (start2 != Integer.MIN_VALUE) {
            set(handle, FILTER2 + FORCE, 0);
        }
        Log.i(TAG, "flat_field: learned from " + learned + " frames");
    }

    private static void done(final String message) {
        MAIN.post(new Runnable() {
            @Override
            public void run() {
                busy = false;
                TextView b = button.get();
                if (b != null) {
                    b.setText(Lang.t(LABEL));
                    b.setAlpha(1f);
                    Toast.makeText(b.getContext(), message, Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private static int get(long handle, int feature, int length) {
        ByteBuffer out = ByteBuffer.allocateDirect(length).order(ByteOrder.LITTLE_ENDIAN);
        int rc = SeekIP.getFeature(handle, feature, out, length);
        if (rc != 0) {
            throw new IllegalStateException("getFeature " + feature + ": " + rc);
        }
        return length == 2 ? out.getShort(0) : out.getInt(0);
    }

    private static void set(long handle, int feature, int value) {
        ByteBuffer in = ByteBuffer.allocateDirect(4).order(ByteOrder.LITTLE_ENDIAN);
        in.putInt(0, value);
        int rc = SeekIP.setFeature(handle, feature, in, 4);
        if (rc != 0) {
            throw new IllegalStateException("setFeature " + feature + ": " + rc);
        }
    }

    /** A view of the app's layout by resource name (the package is the app's, or its resources' after a rename). */
    private static View find(Activity a, String name) {
        String resources = null;
        try {
            resources = a.getResources().getResourcePackageName(a.getApplicationInfo().icon);
        } catch (RuntimeException ignored) {
            // no icon resource: the package name has to do
        }
        for (String p : new String[] {a.getPackageName(), resources}) {
            int id = p == null ? 0 : a.getResources().getIdentifier(name, "id", p);
            if (id != 0) {
                return a.findViewById(id);
            }
        }
        return null;
    }

    private static int dp(Activity a, int dp) {
        return Math.round(dp * a.getResources().getDisplayMetrics().density);
    }
}
