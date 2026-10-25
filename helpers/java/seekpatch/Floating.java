package seekpatch;

import android.app.Activity;
import android.content.Context;
import android.graphics.drawable.GradientDrawable;
import android.preference.PreferenceManager;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * seek-patch's floating buttons below the camera screen's top bar (lock_range, calibration, shutter):
 * a column on each side, so buttons of separate patches stack instead of overlapping, each in a fixed
 * place (its order) whichever patches are applied.
 */
public final class Floating {
    private static final String TAG = "seek-patch";
    private static final String MARK = "seekpatch.floating:";
    private static final int HEIGHT = 28;  // dp
    private static final int GAP = 8;

    private Floating() {
    }

    /** A pill-shaped button; a long press shows tip. */
    public static TextView button(Activity a, final String tip, View.OnClickListener tap) {
        TextView b = new TextView(a);
        b.setTextColor(0xffffffff);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        b.setGravity(Gravity.CENTER);
        b.setSingleLine(true);
        b.setPadding(dp(a, 12), 0, dp(a, 12), 0);
        b.setOnClickListener(tap);
        b.setOnLongClickListener(new View.OnLongClickListener() {
            @Override
            public boolean onLongClick(View v) {
                Toast.makeText(v.getContext(), tip, Toast.LENGTH_LONG).show();
                return true;
            }
        });
        style(b, false);
        return b;
    }

    /** The pill's background: brighter while on. */
    public static void style(TextView b, boolean on) {
        GradientDrawable background = new GradientDrawable();
        background.setCornerRadius(dp(b.getContext(), 14));
        background.setColor(on ? 0x66ffffff : 0x33ffffff);
        background.setStroke(dp(b.getContext(), 1), 0xb3ffffff);
        b.setBackground(background);
    }

    /**
     * After the activity's setContentView: puts b in the column on the right (or left) side below the
     * top bar, at its order (smaller is higher).  False when there is no top bar to put it under.
     */
    public static boolean place(Activity a, View b, boolean right, int order) {
        View bar = find(a, "main_view_top_panel");
        if (bar == null || !(bar.getParent() instanceof FrameLayout)) {
            Log.w(TAG, "no top bar to put a button under (" + bar + ")");
            return false;
        }
        FrameLayout parent = (FrameLayout) bar.getParent();
        String side = MARK + (right ? "right:" : "left:");
        b.setTag(side + order);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(a, HEIGHT),
                Gravity.TOP | (right ? Gravity.RIGHT : Gravity.LEFT));
        if (right) {
            lp.rightMargin = dp(a, 12);
        } else {
            lp.leftMargin = dp(a, 12);
        }
        parent.addView(b, parent.indexOfChild(bar) + 1, lp);  // under the overlays that follow the bar

        List<View> column = new ArrayList<>();
        for (int i = 0; i < parent.getChildCount(); i++) {
            View v = parent.getChildAt(i);
            if (v.getTag() instanceof String && ((String) v.getTag()).startsWith(side)) {
                column.add(v);
            }
        }
        final int skip = side.length();
        Collections.sort(column, new Comparator<View>() {
            @Override
            public int compare(View x, View y) {
                return Integer.parseInt(((String) x.getTag()).substring(skip))
                        - Integer.parseInt(((String) y.getTag()).substring(skip));
            }
        });
        ViewGroup.LayoutParams barParams = bar.getLayoutParams();
        int top = (barParams != null && barParams.height > 0 ? barParams.height : dp(a, 40)) + dp(a, GAP);
        for (View v : column) {
            ((FrameLayout.LayoutParams) v.getLayoutParams()).topMargin = top;
            v.requestLayout();
            top += dp(a, HEIGHT + GAP);
        }
        return true;
    }

    /** The app's temperature unit: 0 Fahrenheit, 1 Celsius (its default), 2 Kelvin. */
    public static int unit(Context c) {
        try {
            return Integer.parseInt(PreferenceManager.getDefaultSharedPreferences(c).getString("units", "1"));
        } catch (RuntimeException e) {
            return 1;
        }
    }

    public static double toUnit(double celsius, int unit) {
        return unit == 0 ? celsius * 1.8 + 32 : unit == 2 ? celsius + 273.15 : celsius;
    }

    public static String symbol(int unit) {
        return unit == 2 ? " K" : unit == 0 ? "°F" : "°C";
    }

    /** A view of the app's layout by resource name (the package is the app's, or its resources' after a rename). */
    public static View find(Activity a, String name) {
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

    public static int dp(Context c, int dp) {
        return Math.round(dp * c.getResources().getDisplayMetrics().density);
    }
}
