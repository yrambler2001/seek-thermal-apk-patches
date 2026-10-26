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
 * one row, the left side's buttons from the left edge in their order, the right side's from the
 * right edge, so buttons of separate patches line up instead of overlapping, each in a fixed place
 * whichever patches are applied.  A button that does not fit in the row (a narrow screen, a long
 * label) goes to the next row down; the rows are laid out again whenever a button's width changes.
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
     * After the activity's setContentView: puts b in the row on the right (or left) side below the
     * top bar, at its order (smaller is nearer the edge).  False when there is no top bar to put it under.
     */
    public static boolean place(Activity a, View b, boolean right, int order) {
        final View bar = find(a, "main_view_top_panel");
        if (bar == null || !(bar.getParent() instanceof FrameLayout)) {
            Log.w(TAG, "no top bar to put a button under (" + bar + ")");
            return false;
        }
        final FrameLayout parent = (FrameLayout) bar.getParent();
        b.setTag(MARK + (right ? "right:" : "left:") + order);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(a, HEIGHT),
                Gravity.TOP | (right ? Gravity.RIGHT : Gravity.LEFT));
        parent.addView(b, parent.indexOfChild(bar) + 1, lp);  // under the overlays that follow the bar
        b.addOnLayoutChangeListener(new View.OnLayoutChangeListener() {
            @Override
            public void onLayoutChange(View v, int l, int t, int r, int bottom, int ol, int ot, int or, int ob) {
                if (r - l != or - ol) {  // a new label: the row may need the space differently
                    v.post(new Runnable() {
                        @Override
                        public void run() {
                            arrange(parent, bar);
                        }
                    });
                }
            }
        });
        arrange(parent, bar);
        return true;
    }

    /** Every button into its place: in order (left first on a tie), each in the first row with room for it. */
    private static void arrange(FrameLayout parent, View bar) {
        Context c = parent.getContext();
        List<View> buttons = new ArrayList<>();
        for (int i = 0; i < parent.getChildCount(); i++) {
            View v = parent.getChildAt(i);
            if (v.getTag() instanceof String && ((String) v.getTag()).startsWith(MARK)) {
                buttons.add(v);
            }
        }
        Collections.sort(buttons, new Comparator<View>() {
            @Override
            public int compare(View x, View y) {
                int byOrder = order(x) - order(y);
                return byOrder != 0 ? byOrder : (right(x) ? 1 : 0) - (right(y) ? 1 : 0);
            }
        });
        int width = parent.getWidth() > 0 ? parent.getWidth() : c.getResources().getDisplayMetrics().widthPixels;
        int edge = dp(c, 12);
        int gap = dp(c, GAP);
        ViewGroup.LayoutParams barParams = bar.getLayoutParams();
        int top = (barParams != null && barParams.height > 0 ? barParams.height : dp(c, 40)) + gap;
        List<int[]> rows = new ArrayList<>();  // each row's free span: {left, right}
        for (View v : buttons) {
            v.measure(View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED),
                    View.MeasureSpec.makeMeasureSpec(dp(c, HEIGHT), View.MeasureSpec.EXACTLY));
            int w = v.getMeasuredWidth();
            int row = 0;
            while (row < rows.size() && rows.get(row)[1] - rows.get(row)[0] < w) {
                row++;
            }
            if (row == rows.size()) {
                rows.add(new int[] {edge, width - edge});
            }
            int[] free = rows.get(row);
            FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) v.getLayoutParams();
            int[] was = {lp.leftMargin, lp.rightMargin, lp.topMargin};
            lp.topMargin = top + row * dp(c, HEIGHT + GAP);
            if (right(v)) {
                lp.leftMargin = 0;
                lp.rightMargin = width - free[1];
                free[1] -= w + gap;
            } else {
                lp.leftMargin = free[0];
                lp.rightMargin = 0;
                free[0] += w + gap;
            }
            if (was[0] != lp.leftMargin || was[1] != lp.rightMargin || was[2] != lp.topMargin) {
                v.requestLayout();
            }
        }
    }

    private static int order(View v) {
        String tag = (String) v.getTag();
        return Integer.parseInt(tag.substring(tag.lastIndexOf(':') + 1));
    }

    private static boolean right(View v) {
        return ((String) v.getTag()).startsWith(MARK + "right:");
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
