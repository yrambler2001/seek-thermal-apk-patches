package seekpatch;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.RelativeLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;

/**
 * seek-thermal-apk-patches smart_smoothing: a "Smart smoothing" button that switches the live image to seek-thermal-apk-patches'
 * motion-compensated noise filter (native library libseekpatch_smooth.so).
 *
 * <p>The filter follows the camera's motion and averages up to eight frames per pixel, so it
 * denoises a hand-held image without the smear of the app's own temporal smoothing, which it
 * replaces while on.  The library hooks the image library's first filter; see
 * docs/smart-smoothing.md.  Off (the default) leaves the app as it was: the library is not even
 * loaded until the first switch on.  The choice is kept in the app's preferences.
 *
 * <p>The state lives in the "seekpatch" preferences: {@link #KEY} (the button), {@link #STRIPES}
 * and {@link #EDGE} (the filter's stripe correction and left-edge levelling, on by default).  The
 * smoothing_settings patch shows the same three keys as switches in Settings, so the button and
 * the switch are one value: a listener keeps the button and the filter in step with the file.
 */
public final class Smooth {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String PREFS = "seekpatch";
    private static final String KEY = "smart_smoothing";
    private static final String STRIPES = "smart_stripes";
    private static final String EDGE = "smart_left_edge";
    /** tnr lines / edge when on ("NR new+LE"); 0 turns each off. */
    private static final int LINES_ON = 3;
    private static final int EDGE_ON = 6;
    private static final String LIBRARY = "seekpatch_smooth";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private static volatile boolean wanted;
    /** bit 0: stripe correction, bit 1: left-edge levelling */
    private static volatile int options = 3;
    private static WeakReference<TextView> button = new WeakReference<>(null);
    private static final SharedPreferences.OnSharedPreferenceChangeListener LISTENER =
            new SharedPreferences.OnSharedPreferenceChangeListener() {
                @Override
                public void onSharedPreferenceChanged(SharedPreferences p, String key) {
                    load(p);  // main thread
                    TextView b = button.get();
                    if (b != null) {
                        show(b);
                    }
                }
            };

    // camera thread
    private static boolean installed;
    private static boolean failed;
    private static boolean applied;
    private static int appliedOptions = -1;

    private Smooth() {
    }

    /** After the activity's setContentView: the button goes into the top bar, left side. */
    public static void attach(Activity a) {
        try {
            SharedPreferences p = prefs(a);
            load(p);
            p.registerOnSharedPreferenceChangeListener(LISTENER);  // held by LISTENER's static field
            View bar = find(a, "main_view_top_panel");
            if (!(bar instanceof RelativeLayout)) {
                Log.w(TAG, "smart_smoothing: no top bar for the button (" + bar + ")");
                return;
            }
            final TextView b = new TextView(a);
            b.setTextColor(0xffffffff);
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            b.setGravity(Gravity.CENTER);
            b.setSingleLine(true);
            b.setPadding(dp(a, 12), 0, dp(a, 12), 0);
            b.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    toggle(b);
                }
            });
            b.setOnLongClickListener(new View.OnLongClickListener() {
                @Override
                public boolean onLongClick(View v) {
                    Toast.makeText(v.getContext(), Lang.t("Motion-compensated noise filter instead of the app's temporal smoothing"),
                            Toast.LENGTH_LONG).show();
                    return true;
                }
            });
            RelativeLayout.LayoutParams lp = new RelativeLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(a, 28));
            lp.addRule(RelativeLayout.ALIGN_PARENT_LEFT);
            lp.addRule(RelativeLayout.CENTER_VERTICAL);
            lp.leftMargin = dp(a, 12);
            ((RelativeLayout) bar).addView(b, lp);
            TopBar.fit(a, bar, b, false);
            button = new WeakReference<>(b);
            show(b);
        } catch (Throwable t) {
            Log.w(TAG, "smart_smoothing: no button", t);
        }
    }

    private static void load(SharedPreferences p) {
        wanted = p.getBoolean(KEY, false);
        options = (p.getBoolean(STRIPES, true) ? 1 : 0) | (p.getBoolean(EDGE, true) ? 2 : 0);
    }

    private static void toggle(TextView b) {
        wanted = !wanted;
        try {
            prefs(b.getContext()).edit().putBoolean(KEY, wanted).apply();
        } catch (RuntimeException e) {
            Log.w(TAG, "smart_smoothing: choice not saved", e);
        }
        show(b);
    }

    private static void show(TextView b) {
        b.setText(wanted ? Lang.t("Smart smoothing on") : Lang.t("Smart smoothing off"));
        GradientDrawable background = new GradientDrawable();
        background.setCornerRadius(dp(b.getContext(), 14));
        background.setColor(wanted ? 0x66ffffff : 0x33ffffff);
        background.setStroke(dp(b.getContext(), 1), 0xb3ffffff);
        b.setBackground(background);
    }

    /** Camera thread, before every frame (after the app's own features). */
    public static void frame() {
        boolean on = wanted;
        int opts = options;
        if (failed || (on == applied && (!installed || opts == appliedOptions))) {
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
            if (opts != appliedOptions) {
                setOptions((opts & 1) != 0 ? LINES_ON : 0, (opts & 2) != 0 ? EDGE_ON : 0);
                appliedOptions = opts;
            }
            if (on != applied) {
                enable(on);
                applied = on;
            }
        } catch (Throwable t) {
            unavailable(String.valueOf(t));
        }
    }

    private static void unavailable(final String why) {
        failed = true;
        Log.w(TAG, "smart_smoothing: unavailable, " + why);
        MAIN.post(new Runnable() {
            @Override
            public void run() {
                TextView b = button.get();
                if (b != null) {
                    Toast.makeText(b.getContext(), Lang.t("Smart smoothing is not available here"), Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    /** Hooks the image library; null when done, else why not (nothing was changed). */
    private static native String install();

    private static native void enable(boolean on);

    /** tnr lines and edge: stripe correction and left-edge levelling, 0 = off. */
    private static native void setOptions(int lines, int edge);

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
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

    private static int dp(Context c, int dp) {
        return Math.round(dp * c.getResources().getDisplayMetrics().density);
    }
}
