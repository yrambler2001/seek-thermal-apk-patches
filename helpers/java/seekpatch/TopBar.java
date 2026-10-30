package seekpatch;

import android.app.Activity;
import android.content.Context;
import android.graphics.Paint;
import android.util.Log;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.List;

/**
 * seek-thermal-apk-patches' buttons in the camera screen's top bar: flat_field's on the right, smart_smoothing's on
 * the left, with the Seek logo and the camera's name ("CompactXR") in the middle.  On a narrow screen (360 dp), with
 * a long label (a translation) or a long camera name, a button would run into the middle.  The middle then moves
 * aside, as far as the other side has room; only what is still missing comes off the button, first from its
 * padding (12 -> 6 dp), then from its text (12 -> 9 sp).  Everything is measured again at every layout of the bar:
 * a new label, the camera's name appearing.
 */
public final class TopBar {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String LEFT = "seekpatch.topbar:left";
    private static final String RIGHT = "seekpatch.topbar:right";
    private static final String[] MIDDLE = {"btn_seekThermal_community", "text_camera_name", "text_camera_type"};
    private static final float SP = 12;
    private static final float MIN_SP = 9;
    private static final int PADDING = 12;  // dp
    private static final int MIN_PADDING = 6;
    private static final int GAP = 8;

    private static WeakReference<View> watched = new WeakReference<>(null);  // main thread

    private TopBar() {
    }

    /** After b was added to the bar, at its right (or left) side. */
    public static void fit(final Activity a, final View bar, TextView b, boolean right) {
        b.setTag(right ? RIGHT : LEFT);
        if (watched.get() == bar) {
            return;  // the other button's call is listening already
        }
        watched = new WeakReference<>(bar);
        bar.addOnLayoutChangeListener(new View.OnLayoutChangeListener() {
            @Override
            public void onLayoutChange(View v, int l, int t, int r, int bottom, int ol, int ot, int or, int ob) {
                try {
                    arrange(a, (ViewGroup) bar);
                } catch (Throwable e) {
                    Log.w(TAG, "top bar: not arranged", e);
                }
            }
        });
    }

    private static void arrange(Activity a, ViewGroup bar) {
        TextView left = null;
        TextView right = null;
        for (int i = 0; i < bar.getChildCount(); i++) {
            View v = bar.getChildAt(i);
            if (LEFT.equals(v.getTag()) && v instanceof TextView && v.getWidth() > 0) {
                left = (TextView) v;
            } else if (RIGHT.equals(v.getTag()) && v instanceof TextView && v.getWidth() > 0) {
                right = (TextView) v;
            }
        }
        int[] at = new int[2];
        bar.getLocationInWindow(at);
        int barLeft = at[0];
        List<View> middle = new ArrayList<>();
        int middleLeft = Integer.MAX_VALUE;
        int middleRight = Integer.MIN_VALUE;
        for (String name : MIDDLE) {
            View m = find(a, name);
            if (m != null && m.getVisibility() == View.VISIBLE && m.getWidth() > 0) {
                m.getLocationInWindow(at);
                int x = at[0] - barLeft - Math.round(m.getTranslationX());  // where the app put it
                middle.add(m);
                middleLeft = Math.min(middleLeft, x);
                middleRight = Math.max(middleRight, x + m.getWidth());
            }
        }
        int gap = dp(a, GAP);
        float shift = 0;
        if (!middle.isEmpty()) {
            // each button at its full size: its outer edge stays where its margin puts it
            int leftEnd = left != null ? left.getLeft() + full(a, left) : 0;
            int rightStart = right != null ? right.getRight() - full(a, right) : bar.getWidth();
            int overRight = middleRight + gap - rightStart;  // > 0: the middle runs under the right button
            int overLeft = leftEnd + gap - middleLeft;
            if (overRight > 0 && overLeft <= 0) {  // to the left, as far as the left button leaves room
                shift = -Math.min(overRight, Math.max(0, middleLeft - leftEnd - gap));
            } else if (overLeft > 0 && overRight <= 0) {
                shift = Math.min(overLeft, Math.max(0, rightStart - gap - middleRight));
            }
            for (View m : middle) {
                if (m.getTranslationX() != shift) {
                    m.setTranslationX(shift);
                }
            }
        }
        int start = middle.isEmpty() ? bar.getWidth() / 2 : Math.round(middleLeft + shift);
        int end = middle.isEmpty() ? bar.getWidth() / 2 : Math.round(middleRight + shift);
        if (right != null) {
            shrink(a, right, right.getRight() - end - gap);
        }
        if (left != null) {
            shrink(a, left, start - gap - left.getLeft());
        }
    }

    /** The button's width with its label at full size. */
    private static int full(Context c, TextView b) {
        return width(c, b, SP) + 2 * dp(c, PADDING);
    }

    /** Fits b into room: less padding first, then a smaller text; at full size when it fits. */
    private static void shrink(Context c, TextView b, int room) {
        int padding = dp(c, PADDING);
        float sp = SP;
        while (padding > dp(c, MIN_PADDING) && width(c, b, sp) + 2 * padding > room) {
            padding -= dp(c, 1);
        }
        while (sp > MIN_SP && width(c, b, sp) + 2 * padding > room) {
            sp -= 0.5f;
        }
        if (Math.abs(b.getTextSize() - px(c, sp)) > 0.01f) {
            b.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        }
        if (b.getPaddingLeft() != padding) {
            b.setPadding(padding, 0, padding, 0);
        }
    }

    private static int width(Context c, TextView b, float sp) {
        Paint p = new Paint(b.getPaint());
        p.setTextSize(px(c, sp));
        return (int) Math.ceil(p.measureText(String.valueOf(b.getText())));
    }

    private static float px(Context c, float sp) {
        return TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, sp, c.getResources().getDisplayMetrics());
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
