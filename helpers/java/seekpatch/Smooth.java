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
 * seek-patch smart_smoothing: a "Smart smoothing" button that switches the live image to seek-patch's
 * motion-compensated noise filter (native library libseekpatch_smooth.so).
 *
 * <p>The filter follows the camera's motion and averages up to eight frames per pixel, so it
 * denoises a hand-held image without the smear of the app's own temporal smoothing, which it
 * replaces while on.  The library hooks the image library's first filter; see
 * docs/smart-smoothing.md.  Off (the default) leaves the app as it was: the library is not even
 * loaded until the first switch on.  The choice is kept in the app's preferences.
 */
public final class Smooth {
    private static final String TAG = "seek-patch";
    private static final String PREFS = "seekpatch";
    private static final String KEY = "smart_smoothing";
    private static final String LIBRARY = "seekpatch_smooth";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private static volatile boolean wanted;
    private static WeakReference<TextView> button = new WeakReference<>(null);

    // camera thread
    private static boolean installed;
    private static boolean failed;
    private static boolean applied;

    private Smooth() {
    }

    /** After the activity's setContentView: the button goes into the top bar, left side. */
    public static void attach(Activity a) {
        try {
            wanted = prefs(a).getBoolean(KEY, false);
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
                    Toast.makeText(v.getContext(), "Motion-compensated noise filter instead of the app's temporal smoothing",
                            Toast.LENGTH_LONG).show();
                    return true;
                }
            });
            RelativeLayout.LayoutParams lp = new RelativeLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(a, 28));
            lp.addRule(RelativeLayout.ALIGN_PARENT_LEFT);
            lp.addRule(RelativeLayout.CENTER_VERTICAL);
            lp.leftMargin = dp(a, 12);
            ((RelativeLayout) bar).addView(b, lp);
            button = new WeakReference<>(b);
            show(b);
        } catch (Throwable t) {
            Log.w(TAG, "smart_smoothing: no button", t);
        }
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
        b.setText(wanted ? "Smart smoothing on" : "Smart smoothing off");
        GradientDrawable background = new GradientDrawable();
        background.setCornerRadius(dp(b.getContext(), 14));
        background.setColor(wanted ? 0x66ffffff : 0x33ffffff);
        background.setStroke(dp(b.getContext(), 1), 0xb3ffffff);
        b.setBackground(background);
    }

    /** Camera thread, before every frame (after the app's own features). */
    public static void frame() {
        boolean on = wanted;
        if (on == applied || failed) {
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
            enable(on);
            applied = on;
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
                    Toast.makeText(b.getContext(), "Smart smoothing is not available here", Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    /** Hooks the image library; null when done, else why not (nothing was changed). */
    private static native String install();

    private static native void enable(boolean on);

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
