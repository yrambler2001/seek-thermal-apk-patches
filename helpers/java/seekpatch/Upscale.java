package seekpatch;

import android.content.SharedPreferences;
import android.preference.PreferenceFragment;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;

/**
 * seek-patch sharp_scaling: its setting, <i>Upscaling</i>, one list from soft to blocky:
 * <pre>
 *     Smooth          the stock Android bilinear scaling (the shader returns the coordinate unchanged)
 *     Sharp 1.5 … 8   the sharp-bilinear shader, blending over 1/N of a pixel (2: as iOS)
 *     Blocky          square pixels: the blend is narrower than an output pixel, the photo unfiltered
 * </pre>
 * It starts from the patch's --sharpness, kept by the fields' initial values; the shader reads
 * {@link SharpScale#sharpness} at every draw, the photo {@link SharpScale#photoFactor}.
 */
public final class Upscale {
    private static final String TAG = "seek-patch";
    private static final String KEY = "upscaling";
    private static final String SMOOTH = "android";
    private static final String BLOCKY = "blocky";
    private static final float[] CHOICES = {1.5f, 2f, 3f, 4f, 6f, 8f};
    /** Blocky's shader sharpness: a blend 1/1000 of a texel wide, far below one output pixel. */
    private static final float BLOCKY_SHARPNESS = 1000f;
    private static final int MAX_PHOTO_FACTOR = 8;
    /** --sharpness: the fields' values before any setting is loaded. */
    private static final float DEFAULT = SharpScale.sharpness;

    private static String loaded;

    private Upscale() {
    }

    /** Settings: the value (main thread). */
    public static void load(SharedPreferences p) {
        String v = value(p);
        String now;
        if (SMOOTH.equals(v)) {
            SharpScale.sharpness = 1f;
            SharpScale.photoFactor = 1;
            now = "smooth (Android's bilinear)";
        } else if (BLOCKY.equals(v)) {
            SharpScale.sharpness = BLOCKY_SHARPNESS;
            SharpScale.photoFactor = 0;
            now = "blocky (photo unfiltered)";
        } else {
            float n = Float.parseFloat(v);
            SharpScale.sharpness = n;
            SharpScale.photoFactor = Math.min(MAX_PHOTO_FACTOR, Math.max(2, Math.round(n)));
            now = "sharp " + v + ", photo " + SharpScale.photoFactor + "x nearest first";
        }
        if (!now.equals(loaded)) {
            loaded = now;
            Log.i(TAG, "sharp_scaling: upscaling " + now);
        }
    }

    /** Settings: the list, appended. */
    public static void screen(PreferenceFragment f, SharedPreferences p) {
        List<String> entries = new ArrayList<>();
        List<String> values = new ArrayList<>();
        entries.add("Smooth: Android's bilinear, blends across each pixel");
        values.add(SMOOTH);
        boolean listed = false;
        for (float c : CHOICES) {
            if (!listed && DEFAULT < c) {
                add(entries, values, DEFAULT);  // a --sharpness between the choices
                listed = true;
            }
            listed |= c == DEFAULT;
            add(entries, values, c);
        }
        if (!listed) {
            add(entries, values, DEFAULT);
        }
        entries.add("Blocky: square pixels, no blending");
        values.add(BLOCKY);
        Settings.addList(f.getPreferenceScreen(), p, KEY, "Upscaling", entries.toArray(new String[0]),
                values.toArray(new String[0]), value(p), null)
                .setDialogTitle("Upscaling: how the camera's pixels are enlarged");
    }

    private static void add(List<String> entries, List<String> values, float n) {
        String label = "Sharp " + text(n) + ": blends " + Math.round(100 / n) + " % of each pixel";
        if (n == 2f) {
            label += ", as iOS";
        }
        if (n == DEFAULT) {
            label += " (default)";
        }
        entries.add(label);
        values.add(text(n));
    }

    /** The stored choice: "android", "blocky" or a sharpness (> 1, at most 16); else --sharpness. */
    private static String value(SharedPreferences p) {
        String v = p.getString(KEY, null);
        if (SMOOTH.equals(v) || BLOCKY.equals(v)) {
            return v;
        }
        try {
            float n = Float.parseFloat(v);
            if (n > 1f && n <= 16f) {
                return text(n);
            }
        } catch (RuntimeException ignored) {
            // none stored, or not a number
        }
        return text(DEFAULT);
    }

    private static String text(float n) {
        return n == Math.rint(n) ? String.valueOf((int) n) : String.valueOf(n);
    }
}
