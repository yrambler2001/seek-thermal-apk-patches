package seekpatch;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;
import java.util.Locale;

/**
 * seek-patch calibration: a button below the camera screen's top bar that sets a linear correction of
 * every temperature, shown = k × measured + b (from a reference thermometer, say).
 *
 * <p>The native library libseekpatch_calib.so hooks libseekip's thermography stage, where each frame is
 * turned into degrees: the per-pixel image and the spot, minimum and maximum get k × t + b there, so the
 * readouts, the temperature bar, saved images and the library's own temperature-driven coloring all
 * agree.  k and b are kept in degrees C (b is entered and shown in the app's unit) and stay set until
 * changed; with k = 1, b = 0 nothing is hooked.  See docs/calibration.md.
 */
public final class Calib {
    private static final String TAG = "seek-patch";
    private static final String LIBRARY = "seekpatch_calib";
    private static final String PREFS = "seekpatch";
    private static final String KEY_K = "calibration_k";
    private static final String KEY_B = "calibration_b";
    private static final String LABEL = "k·x+b";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private static volatile float k = 1f;
    private static volatile float b = 0f;     // °C
    private static volatile boolean changed;  // main thread -> camera thread
    private static WeakReference<TextView> button = new WeakReference<>(null);

    // camera thread
    private static boolean installed;
    private static boolean failed;

    private Calib() {
    }

    /** After the activity's setContentView: the button floats below the top bar, left side, first. */
    public static void attach(final Activity a) {
        try {
            SharedPreferences p = prefs(a);
            float pk = p.getFloat(KEY_K, 1f);
            float pb = p.getFloat(KEY_B, 0f);
            if (valid(pk, pb)) {
                k = pk;
                b = pb;
                changed = true;
            }
            TextView v = Floating.button(a, "Your linear correction of every temperature: shown = k × measured + b",
                    new View.OnClickListener() {
                        @Override
                        public void onClick(View v) {
                            dialog(a);
                        }
                    });
            if (Floating.place(a, v, false, 10)) {
                button = new WeakReference<>(v);
                show(v);
            }
        } catch (Throwable t) {
            Log.w(TAG, "calibration: no button", t);
        }
    }

    private static void dialog(final Activity a) {
        if (failed) {
            Toast.makeText(a, "Calibration is not available here", Toast.LENGTH_SHORT).show();
            return;
        }
        final int unit = Floating.unit(a);
        AlertDialog.Builder builder = new AlertDialog.Builder(a);
        Context c = builder.getContext();
        LinearLayout form = new LinearLayout(c);
        form.setOrientation(LinearLayout.VERTICAL);
        int pad = Floating.dp(c, 20);
        form.setPadding(pad, Floating.dp(c, 8), pad, Floating.dp(c, 12));
        final EditText fk = field(form, "k, the gain (1: none)", format(k));
        final EditText fb = field(form, "b, the offset in " + Floating.symbol(unit).trim() + " (0: none)", format(toUnit(b, k, unit)));
        builder.setTitle("Temperature calibration")
                .setMessage("shown = k × measured + b")
                .setView(form)
                .setPositiveButton("Apply", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        float nk = parse(fk);
                        float nb = parse(fb);
                        if (!valid(nk, nb)) {
                            Toast.makeText(a, "k must be a number above 0, b a number", Toast.LENGTH_LONG).show();
                            return;
                        }
                        save(a, nk, fromUnit(nb, nk, unit));
                    }
                })
                .setNeutralButton("Reset", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int which) {
                        save(a, 1f, 0f);
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private static EditText field(LinearLayout form, String label, String value) {
        Context c = form.getContext();
        TextView title = new TextView(c);
        title.setText(label);
        title.setPadding(0, Floating.dp(c, 8), 0, 0);
        form.addView(title);
        EditText e = new EditText(c);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
        e.setSingleLine(true);
        e.setText(value);
        e.setSelectAllOnFocus(true);
        form.addView(e);
        return e;
    }

    private static void save(Context c, float nk, float nb) {
        prefs(c).edit().putFloat(KEY_K, nk).putFloat(KEY_B, nb).apply();
        k = nk;
        b = nb;
        changed = true;
        Log.i(TAG, "calibration: shown = " + nk + " × measured + " + nb + " °C");
        TextView v = button.get();
        if (v != null) {
            show(v);
        }
    }

    private static void show(TextView v) {
        float ck = k;
        float cb = b;
        boolean on = ck != 1f || cb != 0f;
        if (on) {
            int unit = Floating.unit(v.getContext());
            double bu = toUnit(cb, ck, unit);
            String text = (ck == 1f ? "" : format(ck)) + "x";
            if (Math.abs(bu) >= 0.0005) {  // the unit goes with the offset
                text += (bu < 0 ? " − " : " + ") + format(Math.abs(bu)) + Floating.symbol(unit);
            }
            v.setText(text);
        } else {
            v.setText(LABEL);
        }
        Floating.style(v, on);
    }

    /** Camera thread, before every frame: hooks the library once a correction is set, and passes changes on. */
    public static void frame() {
        if (failed || !changed) {
            return;
        }
        try {
            changed = false;
            float ck = k;
            float cb = b;
            if (!installed) {
                if (ck == 1f && cb == 0f) {
                    return;  // nothing to correct: leave the library alone
                }
                System.loadLibrary(LIBRARY);
                String why = install();
                if (why != null) {
                    unavailable(why);
                    return;
                }
                installed = true;
            }
            set(ck, cb);
        } catch (Throwable t) {
            unavailable(String.valueOf(t));
        }
    }

    private static void unavailable(String why) {
        failed = true;
        Log.w(TAG, "calibration: unavailable, " + why);
        MAIN.post(new Runnable() {
            @Override
            public void run() {
                TextView v = button.get();
                if (v != null) {
                    Toast.makeText(v.getContext(), "Calibration is not available here", Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    /** Hooks the image library; null when done, else why not (nothing was changed). */
    private static native String install();

    /** From the next frame on, every temperature t becomes k × t + b (°C). */
    private static native void set(float k, float b);

    private static boolean valid(float k, float b) {
        return k > 0 && !Float.isInfinite(k) && !Float.isNaN(b) && !Float.isInfinite(b);
    }

    /** b in the app's unit: k × t + b in °C is k × t + b' in °F or K. */
    private static double toUnit(double celsius, double k, int unit) {
        return unit == 0 ? celsius * 1.8 + 32 * (1 - k) : unit == 2 ? celsius + 273.15 * (1 - k) : celsius;
    }

    private static float fromUnit(double b, double k, int unit) {
        return (float) (unit == 0 ? (b - 32 * (1 - k)) / 1.8 : unit == 2 ? b - 273.15 * (1 - k) : b);
    }

    private static float parse(EditText e) {
        try {
            return Float.parseFloat(e.getText().toString().trim().replace(',', '.').replace('−', '-'));
        } catch (RuntimeException ex) {
            return Float.NaN;
        }
    }

    /** Up to three decimals, without trailing zeros. */
    private static String format(double v) {
        String s = String.format(Locale.US, "%.3f", v);
        s = s.replaceAll("0+$", "").replaceAll("\\.$", "");
        return s.equals("-0") ? "0" : s;
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
