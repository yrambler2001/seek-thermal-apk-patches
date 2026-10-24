package seekpatch;

import android.content.SharedPreferences;
import android.preference.ListPreference;
import android.preference.PreferenceFragment;
import android.preference.PreferenceScreen;
import android.preference.SwitchPreference;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;

/**
 * seek-patch sharp_scaling: its settings, <i>iOS-style upscaling</i> (on: the sharp-bilinear shader;
 * off: the stock Android bilinear scaling) and <i>Upscaling sharpness</i> (the blend width, 1/N of a
 * pixel).  They start from the patch's --sharpness, kept by the fields' initial values; the shader
 * reads {@link SharpScale#sharpness} at every draw, the photo {@link SharpScale#photoFactor}.
 * Sharpness 1 is the exact stock sample (the shader returns the coordinate unchanged).
 */
public final class Upscale {
    private static final String TAG = "seek-patch";
    private static final String IOS = "ios_upscaling";
    private static final String SHARPNESS = "upscaling_sharpness";
    private static final float[] CHOICES = {1.5f, 2f, 3f, 4f, 6f, 8f};
    private static final int MAX_PHOTO_FACTOR = 8;
    /** --sharpness: the fields' values before any setting is loaded. */
    private static final float DEFAULT = SharpScale.sharpness;

    private static String loaded;

    private Upscale() {
    }

    /** Settings: the values (main thread). */
    public static void load(SharedPreferences p) {
        boolean ios = p.getBoolean(IOS, true);
        float n = sharpness(p);
        SharpScale.sharpness = ios ? n : 1f;
        SharpScale.photoFactor = ios ? Math.min(MAX_PHOTO_FACTOR, Math.max(2, Math.round(n))) : 1;
        String now = ios ? "iOS, sharpness " + text(n) + ", photo " + SharpScale.photoFactor + "x nearest first"
                : "Android (stock bilinear)";
        if (!now.equals(loaded)) {
            loaded = now;
            Log.i(TAG, "sharp_scaling: upscaling " + now);
        }
    }

    /** Settings: the switch and the list, appended. */
    public static void screen(PreferenceFragment f, final SharedPreferences p) {
        PreferenceScreen s = f.getPreferenceScreen();
        final ListPreference[] list = new ListPreference[1];
        SwitchPreference ios = Settings.addSwitch(s, p, IOS, "iOS-style upscaling", null, true, new Runnable() {
            @Override
            public void run() {
                Settings.enable(list[0], p.getBoolean(IOS, true));
            }
        });
        ios.setSummaryOn("iOS: each pixel stays sharp, blended only at its edges");
        ios.setSummaryOff("Android: smooth bilinear, each pixel blended across its width");
        List<String> entries = new ArrayList<>();
        List<String> values = new ArrayList<>();
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
        list[0] = Settings.addList(s, p, SHARPNESS, "Upscaling sharpness", entries.toArray(new String[0]),
                values.toArray(new String[0]), text(sharpness(p)), null);
        Settings.enable(list[0], p.getBoolean(IOS, true));
    }

    private static void add(List<String> entries, List<String> values, float n) {
        String label = text(n) + ": blends over " + Math.round(100 / n) + " % of each pixel";
        if (n == 2f) {
            label += ", as iOS";
        } else if (n == CHOICES[0]) {
            label += ", softer";
        } else if (n == CHOICES[CHOICES.length - 1]) {
            label += ", nearly blocky";
        }
        if (n == DEFAULT) {
            label += " (default)";
        }
        entries.add(label);
        values.add(text(n));
    }

    private static float sharpness(SharedPreferences p) {
        try {
            float n = Float.parseFloat(p.getString(SHARPNESS, text(DEFAULT)));
            return n > 1f && n <= 16f ? n : DEFAULT;
        } catch (RuntimeException e) {
            return DEFAULT;
        }
    }

    private static String text(float n) {
        return n == Math.rint(n) ? String.valueOf((int) n) : String.valueOf(n);
    }
}
