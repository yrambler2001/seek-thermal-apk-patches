package seekpatch;

import android.app.Activity;
import android.app.Application;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Build;
import android.os.Bundle;
import android.preference.PreferenceActivity;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.util.Log;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsetsController;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * seek-thermal-apk-patches: two touches to the app's own screens, from {@link Settings#attach} (the camera screen's
 * onCreate).
 *
 * <p>The settings screens (PreferencePage, AboutPreferencePage: PreferenceActivity subclasses) have
 * no theme, so on Android 15+ (the app targets SDK 35 and is drawn edge to edge) they get the light
 * system default: a light navigation bar over their black lists, with the white text running under
 * it.  {@link #darkBars} makes the bar dark like the rest of the app, each time such a screen
 * resumes (before its first frame).
 *
 * <p>The side menu (the camera screen's settings panel) gets a divider, in the panel's own style,
 * and "Patched by yrambler2001 v0.4.0" below its last item, Send Feedback: the version is seek-thermal-apk-patches',
 * written into {@link About} when the app was patched.
 */
public final class Screens {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String CREDIT = "Patched by yrambler2001";
    private static boolean registered;  // main thread

    private Screens() {
    }

    /** Camera screen, after setContentView. */
    static void attach(Activity a) {
        if (!registered) {
            registered = true;
            a.getApplication().registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
                @Override
                public void onActivityResumed(Activity activity) {
                    if (activity instanceof PreferenceActivity) {
                        darkBars(activity);
                    }
                }

                @Override
                public void onActivityCreated(Activity activity, Bundle state) {
                }

                @Override
                public void onActivityStarted(Activity activity) {
                }

                @Override
                public void onActivityPaused(Activity activity) {
                }

                @Override
                public void onActivityStopped(Activity activity) {
                }

                @Override
                public void onActivitySaveInstanceState(Activity activity, Bundle state) {
                }

                @Override
                public void onActivityDestroyed(Activity activity) {
                }
            });
        }
        credit(a);
    }

    /** A black window and navigation bar, with a light handle: no light bar, no contrast scrim. */
    static void darkBars(Activity a) {
        try {
            Window w = a.getWindow();
            w.setBackgroundDrawable(new ColorDrawable(Color.BLACK));
            w.setNavigationBarColor(Color.BLACK);  // ignored from Android 15 on, where the bar is transparent
            if (Build.VERSION.SDK_INT >= 29) {
                w.setNavigationBarContrastEnforced(false);
            }
            if (Build.VERSION.SDK_INT >= 30) {
                WindowInsetsController c = w.getInsetsController();
                if (c != null) {
                    c.setSystemBarsAppearance(0, WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
                }
            } else if (Build.VERSION.SDK_INT >= 26) {
                View d = w.getDecorView();
                d.setSystemUiVisibility(d.getSystemUiVisibility() & ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
            }
        } catch (Throwable t) {
            Log.w(TAG, "screens: navigation bar unchanged", t);
        }
    }

    /** Below Send Feedback: a divider like the panel's own (1 px, darker grey, 20 dp around) and the credit, a
     * little smaller than the items and grey, the version greyer, from the panel's left edge. */
    private static void credit(Activity a) {
        try {
            View last = find(a, "settings_send_feedback");
            if (!(last instanceof TextView) || !(last.getParent() instanceof LinearLayout)) {
                Log.w(TAG, "screens: no Send Feedback item for the credit (" + last + ")");
                return;
            }
            TextView feedback = (TextView) last;
            LinearLayout panel = (LinearLayout) feedback.getParent();
            int at = panel.indexOfChild(feedback) + 1;
            View divider = new View(a);
            divider.setBackgroundColor(a.getResources().getColor(android.R.color.darker_gray, null));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1);
            lp.setMargins(0, dp(a, 20), dp(a, 20), dp(a, 20));
            panel.addView(divider, at, lp);
            SpannableStringBuilder text = new SpannableStringBuilder(Lang.t(CREDIT));
            if (About.version != null) {
                int start = text.length();
                text.append(" v").append(About.version);
                text.setSpan(new ForegroundColorSpan(0x73ffffff), start, text.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            TextView credit = new TextView(a);
            credit.setText(text);
            credit.setTypeface(feedback.getTypeface());
            credit.setTextSize(TypedValue.COMPLEX_UNIT_PX, feedback.getTextSize() * 0.85f);
            credit.setTextColor(0xb3ffffff);
            credit.setPadding(0, 0, dp(a, 20), dp(a, 20));
            panel.addView(credit, at + 1, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT));
        } catch (Throwable t) {
            Log.w(TAG, "screens: no credit", t);
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
